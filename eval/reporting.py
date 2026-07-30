"""Reporting engine computing metrics, formatting debug trace outputs, and generating JSON/Markdown reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.config import RESULTS_DIR
from eval.schemas import ScenarioExecutionResult, TurnExecutionResult


def compute_aggregate_metrics(
    results: list[ScenarioExecutionResult],
    mode: str,
    total_latency_ms: int,
) -> dict[str, Any]:
    """Compute comprehensive evaluation metrics across all scenario runs."""
    total_scenarios = len(results)
    passed_scenarios = sum(1 for s in results if s.passed)
    failed_scenarios = total_scenarios - passed_scenarios

    all_turns: list[TurnExecutionResult] = []
    for s in results:
        all_turns.extend(s.turn_results)

    total_turns = len(all_turns)
    passed_turns = sum(1 for t in all_turns if t.passed)

    scen_pass_rate = (passed_scenarios / total_scenarios * 100) if total_scenarios > 0 else 0.0
    turn_pass_rate = (passed_turns / total_turns * 100) if total_turns > 0 else 0.0

    # Categorized assertion failures
    cat_failures: dict[str, list[dict[str, Any]]] = {}
    for s in results:
        for t in s.turn_results:
            for a in t.assertions:
                if not a.passed:
                    if a.category not in cat_failures:
                        cat_failures[a.category] = []
                    cat_failures[a.category].append({
                        "scenario_id": s.scenario_id,
                        "turn_index": t.turn_index,
                        "assertion_name": a.name,
                        "message": a.message,
                    })

    # Routing metrics
    route_assertions = [
        a for t in all_turns for a in t.assertions if a.category == "routing"
    ]
    route_accuracy = (
        (sum(1 for a in route_assertions if a.passed) / len(route_assertions) * 100)
        if route_assertions
        else 100.0
    )

    fallback_count = sum(1 for t in all_turns if t.route_source == "deterministic_fallback")
    fallback_rate = (fallback_count / total_turns * 100) if total_turns > 0 else 0.0

    # Tool selection metrics
    tool_req_assertions = [
        a for t in all_turns for a in t.assertions if a.name == "required_tools"
    ]
    required_tool_recall = (
        (sum(1 for a in tool_req_assertions if a.passed) / len(tool_req_assertions) * 100)
        if tool_req_assertions
        else 100.0
    )

    tool_forbid_assertions = [
        a for t in all_turns for a in t.assertions if a.name == "forbidden_tools"
    ]
    forbidden_tool_violation_rate = (
        (sum(1 for a in tool_forbid_assertions if not a.passed) / len(tool_forbid_assertions) * 100)
        if tool_forbid_assertions
        else 0.0
    )

    # Multi-turn & state leak metrics
    multi_turn_scenarios = [s for s in results if len(s.turn_results) > 1]
    multi_turn_passed = sum(1 for s in multi_turn_scenarios if s.passed)
    multi_turn_completion_rate = (
        (multi_turn_passed / len(multi_turn_scenarios) * 100)
        if multi_turn_scenarios
        else 100.0
    )

    stale_assertions = [
        a for t in all_turns for a in t.assertions if a.name == "no_stale_citations"
    ]
    stale_citation_rate = (
        (sum(1 for a in stale_assertions if not a.passed) / len(stale_assertions) * 100)
        if stale_assertions
        else 0.0
    )

    # Follow-ups metrics
    turns_with_followups = sum(1 for t in all_turns if len(t.followups) > 0)
    followup_presence_rate = (turns_with_followups / total_turns * 100) if total_turns > 0 else 0.0

    # Latency percentiles
    latencies = sorted([t.latency_ms for t in all_turns])
    mean_lat = sum(latencies) / len(latencies) if latencies else 0.0
    p50_lat = latencies[int(len(latencies) * 0.5)] if latencies else 0
    p95_lat = latencies[int(len(latencies) * 0.95)] if latencies else 0

    return {
        "mode": mode,
        "total_scenarios": total_scenarios,
        "passed_scenarios": passed_scenarios,
        "failed_scenarios": failed_scenarios,
        "errored_scenarios": sum(1 for s in results if any(t.error_message for t in s.turn_results)),
        "total_turns": total_turns,
        "passed_turns": passed_turns,
        "scenario_pass_rate": round(scen_pass_rate, 2),
        "turn_pass_rate": round(turn_pass_rate, 2),
        "routing": {
            "route_accuracy": round(route_accuracy, 2),
            "fallback_route_rate": round(fallback_rate, 2),
        },
        "tool_orchestration": {
            "required_tool_recall": round(required_tool_recall, 2),
            "forbidden_tool_violation_rate": round(forbidden_tool_violation_rate, 2),
        },
        "multi_turn": {
            "multi_turn_scenarios_count": len(multi_turn_scenarios),
            "multi_turn_completion_rate": round(multi_turn_completion_rate, 2),
            "stale_citation_rate": round(stale_citation_rate, 2),
        },
        "followups": {
            "followup_presence_rate": round(followup_presence_rate, 2),
        },
        "performance": {
            "mean_latency_ms": round(mean_lat, 2),
            "p50_latency_ms": p50_lat,
            "p95_latency_ms": p95_lat,
        },
        "failures_by_category": cat_failures,
    }


def write_run_reports(
    run_id: str,
    run_dir: Path,
    metadata: dict[str, Any],
    results: list[ScenarioExecutionResult],
    metrics: dict[str, Any],
):
    """Write structured JSON, JSONL logs, and Markdown reports to run directory."""
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. metadata.json
    with open(run_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # 2. summary.json
    with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    # 3. failures.json
    with open(run_dir / "failures.json", "w", encoding="utf-8") as f:
        json.dump(metrics.get("failures_by_category", {}), f, ensure_ascii=False, indent=2)

    # 4. events.jsonl
    with open(run_dir / "events.jsonl", "w", encoding="utf-8") as f:
        seq = 1
        for s in results:
            for t in s.turn_results:
                for trace in t.tool_traces:
                    event = {
                        "run_id": run_id,
                        "scenario_id": s.scenario_id,
                        "turn_index": t.turn_index,
                        "sequence": seq,
                        "event_type": "tool_end",
                        "tool": trace.get("tool"),
                        "status": trace.get("status"),
                        "latency_ms": trace.get("latency_ms", 0),
                        "details": trace.get("details", {}),
                    }
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
                    seq += 1

    # 5. turns.jsonl
    with open(run_dir / "turns.jsonl", "w", encoding="utf-8") as f:
        for s in results:
            for t in s.turn_results:
                turn_dict = {
                    "scenario_id": s.scenario_id,
                    "turn_index": t.turn_index,
                    "input_type": t.input_type,
                    "input": t.input_text,
                    "route": t.route,
                    "route_source": t.route_source,
                    "status": t.status,
                    "assistant_message": t.assistant_message,
                    "citation_ids": t.citation_ids,
                    "citation_pages": t.citation_pages,
                    "followups": t.followups,
                    "tool_sequence": t.tool_sequence,
                    "passed": t.passed,
                    "latency_ms": t.latency_ms,
                    "assertions": [a.model_dump() for a in t.assertions],
                }
                f.write(json.dumps(turn_dict, ensure_ascii=False) + "\n")

    # 6. report.md
    report_md = _generate_markdown_report(run_id, metadata, results, metrics)
    with open(run_dir / "report.md", "w", encoding="utf-8") as f:
        f.write(report_md)

    # Also update root eval/results/ report and results.json
    root_results_dir = RESULTS_DIR
    root_results_dir.mkdir(parents=True, exist_ok=True)
    with open(root_results_dir / "report.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    with open(root_results_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)


def _generate_markdown_report(
    run_id: str,
    metadata: dict[str, Any],
    results: list[ScenarioExecutionResult],
    metrics: dict[str, Any],
) -> str:
    """Generate Markdown report for evaluation evidence deliverable."""
    scen_pass = metrics.get("passed_scenarios", 0)
    scen_total = metrics.get("total_scenarios", 0)
    scen_rate = metrics.get("scenario_pass_rate", 0.0)

    perf = metrics.get("performance", {})
    route_m = metrics.get("routing", {})
    tool_m = metrics.get("tool_orchestration", {})
    mt_m = metrics.get("multi_turn", {})

    md = f"""# Bảng Kết Quả Đánh Giá VLearn Evaluation Evidence

**Run ID**: `{run_id}`
**Git SHA**: `{metadata.get("git_sha", "unknown")}` (`{metadata.get("git_branch", "main")}`)
**Mode**: `{metadata.get("mode", "offline")}` ({metadata.get("model", "fake")})
**Scenario Pass Rate**: {scen_pass} / {scen_total} (**{scen_rate:.1f}%**)
**Turn Pass Rate**: {metrics.get("passed_turns", 0)} / {metrics.get("total_turns", 0)} (**{metrics.get("turn_pass_rate", 0.0):.1f}%**)
**Average Latency**: {perf.get("mean_latency_ms", 0)} ms (P50: {perf.get("p50_latency_ms", 0)} ms, P95: {perf.get("p95_latency_ms", 0)} ms)

---

## 1. Metric Summaries

### Routing & Classification
* **Route Accuracy**: {route_m.get("route_accuracy", 0.0)}%
* **Deterministic Fallback Rate**: {route_m.get("fallback_route_rate", 0.0)}%

### Tool Orchestration
* **Required Tool Recall**: {tool_m.get("required_tool_recall", 0.0)}%
* **Forbidden Tool Violation Rate**: {tool_m.get("forbidden_tool_violation_rate", 0.0)}%

### Multi-Turn & Interrupt/Resume
* **Multi-Turn Scenarios Tested**: {mt_m.get("multi_turn_scenarios_count", 0)}
* **Multi-Turn Completion Rate**: {mt_m.get("multi_turn_completion_rate", 0.0)}%
* **Stale Citation Rate**: {mt_m.get("stale_citation_rate", 0.0)}%

---

## 2. Detailed Scenario Results

| Scenario ID | Name | Tags | Turns | Pass/Fail | Failure Reasons |
|---|---|---|---|---|---|
"""
    for s in results:
        status_str = "✅ PASS" if s.passed else "❌ FAIL"
        tags_str = ", ".join(s.tags)
        reasons_str = "; ".join(s.failure_reasons) if s.failure_reasons else "None"
        md += f"| {s.scenario_id} | {s.name} | {tags_str} | {len(s.turn_results)} | {status_str} | {reasons_str} |\n"

    # Failures by Category Breakdown
    cat_failures = metrics.get("failures_by_category", {})
    if cat_failures:
        md += "\n--- \n\n## 3. Failure Breakdown by Category\n\n"
        for cat, items in cat_failures.items():
            md += f"### Category: `{cat}` ({len(items)} failures)\n"
            for item in items:
                md += f"- **[{item['scenario_id']} - Turn {item['turn_index']}]** {item['assertion_name']}: {item['message']}\n"

    return md


def print_turn_debug_trace(
    turn_res: TurnExecutionResult,
    verbose: bool = False,
):
    """Print formatted debug progression for console output."""
    pass_mark = "✅ PASS" if turn_res.passed else "❌ FAIL"
    print(f"\n   Turn {turn_res.turn_index} [{turn_res.input_type}]: '{turn_res.input_text[:50]}...' -> {pass_mark}")
    print(f"   Route: {turn_res.route} ({turn_res.route_source}) | Status: {turn_res.status} | Latency: {turn_res.latency_ms} ms")

    if turn_res.retrieved_sources:
        print(f"   Retrieved Sources: {', '.join(turn_res.retrieved_sources[:3])}")

    if turn_res.tool_sequence:
        print(f"   Tool Progression: {' -> '.join(turn_res.tool_sequence)}")

    if turn_res.citation_ids:
        print(f"   Citations: {turn_res.citation_ids}")

    if verbose:
        print(f"\n   Assistant Response:\n   {turn_res.assistant_message or '(None)'}")
        print("\n   Assertions:")
        for a in turn_res.assertions:
            mark = "✅ PASS" if a.passed else "❌ FAIL"
            print(f"     [{mark}] {a.name}: {a.message}")
