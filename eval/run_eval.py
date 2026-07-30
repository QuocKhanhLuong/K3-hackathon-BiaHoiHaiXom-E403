"""Thin CLI entrypoint for VLearn Evaluation Framework."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add repo root to sys.path
EVAL_DIR = Path(__file__).resolve().parent
ROOT_DIR = EVAL_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from eval.config import (
    DEFAULT_LIVE_MODEL,
    DEFAULT_OFFLINE_MODEL,
    RESULTS_DIR,
    SCENARIOS_DIR,
)
from eval.context_provider import EvalContextProvider
from eval.reporting import (
    compute_aggregate_metrics,
    print_turn_debug_trace,
    write_run_reports,
)
from eval.runner import ScenarioRunner
from eval.schemas import ScenarioDefinition, ScenarioExecutionResult


def load_all_scenarios(
    scenarios_dir: Path,
    tags_filter: list[str] | None = None,
    scenario_id_filter: str | None = None,
    mode: str | None = None,
) -> list[ScenarioDefinition]:
    """Load and validate all JSON scenario definitions from scenarios directory."""
    scenarios: list[ScenarioDefinition] = []
    if not scenarios_dir.exists():
        return scenarios

    for json_file in sorted(scenarios_dir.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        scen = ScenarioDefinition(**item)
                        scenarios.append(scen)
        except Exception as exc:
            print(f"[Eval Warning] Failed to load scenario file {json_file.name}: {exc}")

    # Apply filters
    if scenario_id_filter:
        scenarios = [s for s in scenarios if s.id == scenario_id_filter]

    if tags_filter:
        filter_set = {t.strip().lower() for t in tags_filter}
        scenarios = [
            s for s in scenarios if any(tag.lower() in filter_set for tag in s.tags)
        ]

    if mode:
        scenarios = [s for s in scenarios if s.mode in {mode, "both"}]

    return scenarios


async def main():
    parser = argparse.ArgumentParser(description="VLearn AI Core Evaluation Framework")
    parser.add_argument(
        "--mode",
        choices=["offline", "live"],
        default="offline",
        help="Evaluation execution mode (offline=fake model, live=OpenAI model)",
    )
    parser.add_argument("--tags", type=str, help="Comma-separated tag filter (e.g. multi_turn,followup)")
    parser.add_argument("--scenario", type=str, help="Specific scenario ID filter (e.g. MT-REPAIR-001)")
    parser.add_argument("--max-cases", type=int, help="Maximum number of scenarios to run")
    parser.add_argument("--verbose", action="store_true", help="Print detailed debug traces for each turn")
    parser.add_argument("--stream-events", action="store_true", help="Stream tool events in real time")
    parser.add_argument("--fail-fast", action="store_true", help="Stop execution immediately on first failure")
    parser.add_argument("--output-dir", type=str, help="Custom output directory for run reports")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat scenario execution count")
    parser.add_argument("--judge", action="store_true", help="Enable LLM-as-a-Judge for soft quality scoring")
    parser.add_argument("--no-judge", action="store_true", help="Disable LLM-as-a-Judge")
    parser.add_argument("--model", type=str, help="Override LLM model name")

    args = parser.parse_args()

    mode = args.mode
    api_key = os.environ.get("OPENAI_API_KEY", "")
    run_live_env = os.environ.get("RUN_LIVE_TESTS", "") == "1"

    # Enforce live mode gate: requires both --mode live AND RUN_LIVE_TESTS=1 AND OPENAI_API_KEY
    if mode == "live" and (not run_live_env or not api_key):
        print("[Eval Gate] Live mode requested but RUN_LIVE_TESTS=1 or OPENAI_API_KEY is missing.")
        print("[Eval Gate] Falling back to OFFLINE mode for safety.")
        mode = "offline"

    model_name = (
        args.model
        or (DEFAULT_LIVE_MODEL if mode == "live" else DEFAULT_OFFLINE_MODEL)
    )

    tags_filter = [t.strip() for t in args.tags.split(",")] if args.tags else None
    scenarios = load_all_scenarios(SCENARIOS_DIR, tags_filter=tags_filter, scenario_id_filter=args.scenario, mode=mode)

    if not scenarios:
        print("[Eval Error] No scenarios found matching filters.")
        sys.exit(1)

    if args.max_cases and args.max_cases > 0:
        scenarios = scenarios[: args.max_cases]

    total_scenarios = len(scenarios) * args.repeat
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{mode}"
    run_dir = Path(args.output_dir) if args.output_dir else RESULTS_DIR / run_id

    print("\n========================================================")
    print("  VLearn Evaluation Framework")
    print(f"  Run ID: {run_id}")
    print(f"  Mode: {mode.upper()} ({model_name})")
    print(f"  Total Scenarios: {total_scenarios}")
    print(f"  Selected by mode: {len(scenarios)} ({mode} or both)")
    print("========================================================\n")

    context_provider = EvalContextProvider()
    runner = ScenarioRunner(
        mode=mode,
        model_name=model_name,
        api_key=api_key,
        use_judge=args.judge and not args.no_judge,
        context_provider=context_provider,
    )

    results: list[ScenarioExecutionResult] = []
    total_start_time = time.time()

    for rep in range(args.repeat):
        for idx, scenario in enumerate(scenarios, start=1):
            curr_idx = rep * len(scenarios) + idx
            print(f"[{curr_idx}/{total_scenarios}] Running Scenario: {scenario.id} — {scenario.name}")

            res = await runner.run_scenario(scenario, verbose=args.verbose)
            results.append(res)

            for t_res in res.turn_results:
                print_turn_debug_trace(t_res, verbose=args.verbose)

            if not res.passed and args.fail_fast:
                print(f"\n[Fail-Fast] Stopping run on scenario {scenario.id}")
                break

    total_run_latency_ms = int((time.time() - total_start_time) * 1000)

    # Git metadata
    try:
        import subprocess

        git_sha = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR)
            .decode()
            .strip()
        )
        git_branch = (
            subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT_DIR)
            .decode()
            .strip()
        )
    except Exception:
        git_sha = "unknown"
        git_branch = "unknown"

    metadata = {
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": git_sha,
        "git_branch": git_branch,
        "mode": mode,
        "model": model_name,
        "seed": args.seed,
        "repeat": args.repeat,
        "scenario_count": total_scenarios,
        "judge_enabled": args.judge and not args.no_judge,
        "live_api_called": mode == "live",
    }

    metrics = compute_aggregate_metrics(results, mode, total_run_latency_ms)
    write_run_reports(run_id, run_dir, metadata, results, metrics)

    scen_pass = metrics.get("scenario_pass_rate", {})
    pass_count = scen_pass.get("passed_count", 0)
    eval_count = scen_pass.get("evaluated_count", 0)
    rate_val = scen_pass.get("value")
    rate_str = f"{rate_val:.1f}%" if rate_val is not None else "NOT EVALUATED"

    print("\n========================================================")
    print(f"  Eval Completed! Passed: {pass_count}/{eval_count} evaluated scenarios ({rate_str})")
    print(f"  Report written to: {run_dir / 'report.md'}")
    print("========================================================\n")

    if pass_count < total_scenarios and args.fail_fast:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
