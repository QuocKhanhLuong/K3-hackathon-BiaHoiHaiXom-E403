"""Reporting engine computing explicit metrics, logging event streams, and formatting public response traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.config import RESULTS_DIR
from eval.schemas import MetricValue, ScenarioExecutionResult, TurnExecutionResult


def _make_metric(evaluated_count: int, passed_count: int) -> MetricValue:
    """Build MetricValue model returning null value and status='not_evaluated' if evaluated_count is 0."""
    if evaluated_count == 0:
        return MetricValue(
            value=None,
            evaluated_count=0,
            passed_count=0,
            failed_count=0,
            status="not_evaluated",
        )
    val = round(passed_count / evaluated_count * 100.0, 2)
    return MetricValue(
        value=val,
        evaluated_count=evaluated_count,
        passed_count=passed_count,
        failed_count=evaluated_count - passed_count,
        status="evaluated",
    )


def compute_aggregate_metrics(
    results: list[ScenarioExecutionResult],
    mode: str,
    total_latency_ms: int,
) -> dict[str, Any]:
    """Compute explicit evaluation metrics with zero-denominator handling across scenarios."""
    # Separate scenario tiers
    gold_results = [
        s for s in results if s.tier == "gold" and s.evaluation_type == "hard"
    ]
    coverage_results = [
        s for s in results if s.tier == "coverage" and s.evaluation_type == "hard"
    ]
    exploratory_results = [s for s in results if s.evaluation_type == "exploratory"]

    total_scenarios = len(results)
    eval_scenarios = gold_results + coverage_results

    scen_metric = _make_metric(
        len(eval_scenarios), sum(1 for s in eval_scenarios if s.passed)
    )
    gold_scen_metric = _make_metric(
        len(gold_results), sum(1 for s in gold_results if s.passed)
    )
    cov_scen_metric = _make_metric(
        len(coverage_results), sum(1 for s in coverage_results if s.passed)
    )

    all_eval_turns: list[TurnExecutionResult] = [
        t for s in eval_scenarios for t in s.turn_results
    ]

    turn_metric = _make_metric(
        len(all_eval_turns), sum(1 for t in all_eval_turns if t.passed)
    )

    # Categorized assertion failures
    cat_failures: dict[str, list[dict[str, Any]]] = {}
    for s in results:
        for t in s.turn_results:
            for a in t.assertions:
                if not a.passed:
                    if a.category not in cat_failures:
                        cat_failures[a.category] = []
                    cat_failures[a.category].append(
                        {
                            "scenario_id": s.scenario_id,
                            "turn_index": t.turn_index,
                            "assertion_name": a.name,
                            "message": a.message,
                        }
                    )

    # Metric Evaluators
    route_assertions = [
        a for t in all_eval_turns for a in t.assertions if a.category == "routing"
    ]
    route_metric = _make_metric(
        len(route_assertions), sum(1 for a in route_assertions if a.passed)
    )

    tool_req_assertions = [
        a for t in all_eval_turns for a in t.assertions if a.name == "required_tools"
    ]
    tool_req_metric = _make_metric(
        len(tool_req_assertions), sum(1 for a in tool_req_assertions if a.passed)
    )

    tool_forbid_assertions = [
        a for t in all_eval_turns for a in t.assertions if a.name == "forbidden_tools"
    ]
    tool_forbid_metric = _make_metric(
        len(tool_forbid_assertions), sum(1 for a in tool_forbid_assertions if a.passed)
    )

    multi_turn_scenarios = [s for s in eval_scenarios if len(s.turn_results) > 1]
    mt_metric = _make_metric(
        len(multi_turn_scenarios), sum(1 for s in multi_turn_scenarios if s.passed)
    )

    stale_assertions = [
        a
        for t in all_eval_turns
        for a in t.assertions
        if a.name == "no_stale_citations"
    ]
    stale_metric = _make_metric(
        len(stale_assertions), sum(1 for a in stale_assertions if a.passed)
    )

    followup_assertions = [
        a for t in all_eval_turns for a in t.assertions if a.category == "followup"
    ]
    followup_metric = _make_metric(
        len(followup_assertions), sum(1 for a in followup_assertions if a.passed)
    )

    grounding_assertions = [
        a for t in all_eval_turns for a in t.assertions if a.category == "grounding"
    ]
    grounding_metric = _make_metric(
        len(grounding_assertions), sum(1 for a in grounding_assertions if a.passed)
    )

    repair_assertions = [
        a for t in all_eval_turns for a in t.assertions if a.category == "repair"
    ]
    repair_metric = _make_metric(
        len(repair_assertions), sum(1 for a in repair_assertions if a.passed)
    )

    # Latency percentiles
    latencies = sorted([t.latency_ms for t in all_eval_turns])
    mean_lat = sum(latencies) / len(latencies) if latencies else 0.0
    p50_lat = latencies[int(len(latencies) * 0.5)] if latencies else 0
    p95_lat = latencies[int(len(latencies) * 0.95)] if latencies else 0

    return {
        "mode": mode,
        "total_scenarios": total_scenarios,
        "evaluated_scenarios_count": len(eval_scenarios),
        "exploratory_scenario_count": len(exploratory_results),
        "scenario_pass_rate": scen_metric.model_dump(),
        "gold_scenario_pass_rate": gold_scen_metric.model_dump(),
        "coverage_scenario_pass_rate": cov_scen_metric.model_dump(),
        "turn_pass_rate": turn_metric.model_dump(),
        "routing": {
            "route_accuracy": route_metric.model_dump(),
        },
        "tool_orchestration": {
            "required_tool_recall": tool_req_metric.model_dump(),
            "forbidden_tool_violation_rate": tool_forbid_metric.model_dump(),
        },
        "multi_turn": {
            "multi_turn_completion_rate": mt_metric.model_dump(),
            "stale_citation_rate": stale_metric.model_dump(),
        },
        "followups": {
            "followup_quality_pass_rate": followup_metric.model_dump(),
        },
        "grounding": {
            "grounding_pass_rate": grounding_metric.model_dump(),
        },
        "repair": {
            "misconception_repair_pass_rate": repair_metric.model_dump(),
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

    with open(run_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    with open(run_dir / "failures.json", "w", encoding="utf-8") as f:
        json.dump(
            metrics.get("failures_by_category", {}), f, ensure_ascii=False, indent=2
        )

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
                    "response_origin": t.response_origin,
                    "public_response": t.public_response,
                    "safe_state_snapshot": t.safe_state_snapshot,
                    "faults_triggered": t.faults_triggered,
                    "citation_ids": t.citation_ids,
                    "citation_pages": t.citation_pages,
                    "followups": t.followups,
                    "tool_sequence": t.tool_sequence,
                    "passed": t.passed,
                    "latency_ms": t.latency_ms,
                    "blocked_by_previous_turn": t.blocked_by_previous_turn,
                    "grounding_valid": t.grounding_valid,
                    "grounding_error": t.grounding_error,
                    "grounding_failure_type": t.grounding_failure_type,
                    "grounding_retry_count": t.grounding_retry_count,
                    "grounding_invalid_citation_ids": t.grounding_invalid_citation_ids,
                    "grounding_uncovered_sentences": t.grounding_uncovered_sentences,
                    "candidate_answer": t.candidate_answer,
                    "candidate_claims": t.candidate_claims,
                    "candidate_citations": t.candidate_citations,
                    "failure_code": t.failure_code,
                    "failure_stage": t.failure_stage,
                    "assertions": [a.model_dump() for a in t.assertions],
                }
                f.write(json.dumps(turn_dict, ensure_ascii=False) + "\n")

    report_md = _generate_markdown_report(run_id, metadata, results, metrics)
    with open(run_dir / "report.md", "w", encoding="utf-8") as f:
        f.write(report_md)

    # Update root deliverables
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
    scen_m = metrics.get("scenario_pass_rate", {})
    gold_m = metrics.get("gold_scenario_pass_rate", {})
    perf = metrics.get("performance", {})

    scen_val = scen_m.get("value")
    scen_str = f"{scen_val:.1f}%" if scen_val is not None else "NOT EVALUATED"

    gold_val = gold_m.get("value")
    gold_str = f"{gold_val:.1f}%" if gold_val is not None else "NOT EVALUATED"

    md = f"""# Bảng Kết Quả Đánh Giá VLearn Evaluation Evidence

**Run ID**: `{run_id}`
**Git SHA**: `{metadata.get("git_sha", "unknown")}` (`{metadata.get("git_branch", "main")}`)
**Mode**: `{metadata.get("mode", "offline")}` ({metadata.get("model", "scripted")})
**Gold Scenario Pass Rate**: {gold_m.get("passed_count", 0)} / {gold_m.get("evaluated_count", 0)} (**{gold_str}**)
**Overall Scenario Pass Rate**: {scen_m.get("passed_count", 0)} / {scen_m.get("evaluated_count", 0)} (**{scen_str}**)
**Average Latency**: {perf.get("mean_latency_ms", 0)} ms (P50: {perf.get("p50_latency_ms", 0)} ms, P95: {perf.get("p95_latency_ms", 0)} ms)

---

## 1. Detailed Metric Breakdown

| Metric Group | Metric Name | Value | Evaluated Count | Status |
|---|---|---|---|---|
| Routing | Route Accuracy | {metrics.get("routing", {}).get("route_accuracy", {}).get("value")}% | {metrics.get("routing", {}).get("route_accuracy", {}).get("evaluated_count")} | {metrics.get("routing", {}).get("route_accuracy", {}).get("status")} |
| Orchestration | Required Tool Recall | {metrics.get("tool_orchestration", {}).get("required_tool_recall", {}).get("value")}% | {metrics.get("tool_orchestration", {}).get("required_tool_recall", {}).get("evaluated_count")} | {metrics.get("tool_orchestration", {}).get("required_tool_recall", {}).get("status")} |
| Orchestration | Forbidden Tool Violations | {metrics.get("tool_orchestration", {}).get("forbidden_tool_violation_rate", {}).get("value")}% | {metrics.get("tool_orchestration", {}).get("forbidden_tool_violation_rate", {}).get("evaluated_count")} | {metrics.get("tool_orchestration", {}).get("forbidden_tool_violation_rate", {}).get("status")} |
| Multi-Turn | Completion Rate | {metrics.get("multi_turn", {}).get("multi_turn_completion_rate", {}).get("value")}% | {metrics.get("multi_turn", {}).get("multi_turn_completion_rate", {}).get("evaluated_count")} | {metrics.get("multi_turn", {}).get("multi_turn_completion_rate", {}).get("status")} |
| Multi-Turn | Stale Citation Pass Rate | {metrics.get("multi_turn", {}).get("stale_citation_rate", {}).get("value")}% | {metrics.get("multi_turn", {}).get("stale_citation_rate", {}).get("evaluated_count")} | {metrics.get("multi_turn", {}).get("stale_citation_rate", {}).get("status")} |
| Grounding | Grounding Pass Rate | {metrics.get("grounding", {}).get("grounding_pass_rate", {}).get("value")}% | {metrics.get("grounding", {}).get("grounding_pass_rate", {}).get("evaluated_count")} | {metrics.get("grounding", {}).get("grounding_pass_rate", {}).get("status")} |
| Repair | Repair Pass Rate | {metrics.get("repair", {}).get("misconception_repair_pass_rate", {}).get("value")}% | {metrics.get("repair", {}).get("misconception_repair_pass_rate", {}).get("evaluated_count")} | {metrics.get("repair", {}).get("misconception_repair_pass_rate", {}).get("status")} |

---

## 2. Detailed Scenario Results

| Scenario ID | Name | Tier | Evaluation Type | Pass/Fail | Failure Reasons |
|---|---|---|---|---|---|
"""
    for s in results:
        status_str = "✅ PASS" if s.passed else "❌ FAIL"
        reasons_str = "; ".join(s.failure_reasons) if s.failure_reasons else "None"
        md += f"| {s.scenario_id} | {s.name} | {s.tier} | {s.evaluation_type} | {status_str} | {reasons_str} |\n"

    return md


def print_turn_debug_trace(
    turn_res: TurnExecutionResult,
    verbose: bool = False,
):
    """Print formatted public response and safe state debug trace for console output."""
    pass_mark = "✅ PASS" if turn_res.passed else "❌ FAIL"
    print(
        f"\n   Turn {turn_res.turn_index} [{turn_res.input_type}]: '{turn_res.input_text[:50]}...' -> {pass_mark}"
    )
    print(f"   Response Origin: {turn_res.response_origin}")
    print(
        f"   Route: {turn_res.route} ({turn_res.route_source}) | Status: {turn_res.status} | Latency: {turn_res.latency_ms} ms"
    )

    if turn_res.faults_triggered:
        print(f"   Faults Triggered: {turn_res.faults_triggered}")

    if turn_res.retrieved_sources:
        print(f"   Retrieved Sources: {', '.join(turn_res.retrieved_sources[:4])}")

    if turn_res.tool_sequence:
        print(f"   Tool Progression: {' -> '.join(turn_res.tool_sequence)}")

    if verbose:
        if turn_res.public_response:
            print("\n   Public Response:")
            print(json.dumps(turn_res.public_response, ensure_ascii=False, indent=4))

        if turn_res.safe_state_snapshot:
            print("\n   Safe State Snapshot:")
            print(
                json.dumps(turn_res.safe_state_snapshot, ensure_ascii=False, indent=4)
            )

        print("\n   Assertions:")
        for a in turn_res.assertions:
            mark = "✅ PASS" if a.passed else "❌ FAIL"
            print(f"     [{mark}] {a.name}: {a.message}")
