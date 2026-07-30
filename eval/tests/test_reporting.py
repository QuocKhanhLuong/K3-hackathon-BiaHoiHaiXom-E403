"""Unit tests for reporting metrics computation and report writing."""

import tempfile
from pathlib import Path

from eval.reporting import compute_aggregate_metrics, write_run_reports
from eval.schemas import ScenarioExecutionResult, TurnExecutionResult


def test_compute_aggregate_metrics():
    turn1 = TurnExecutionResult(
        scenario_id="SCEN-1",
        turn_index=1,
        input_type="user_turn",
        input_text="Question 1",
        route="simple",
        route_source="structured_model",
        status="completed",
        assistant_message="Answer 1",
        passed=True,
        latency_ms=100,
    )
    scen1 = ScenarioExecutionResult(
        scenario_id="SCEN-1",
        name="Scenario 1",
        tags=["simple"],
        passed=True,
        turn_results=[turn1],
        total_latency_ms=100,
    )

    metrics = compute_aggregate_metrics([scen1], mode="offline", total_latency_ms=100)
    assert metrics["total_scenarios"] == 1
    assert metrics["passed_scenarios"] == 1
    assert metrics["scenario_pass_rate"] == 100.0


def test_write_run_reports_generates_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        run_dir = Path(tmpdir) / "run_test"
        turn1 = TurnExecutionResult(
            scenario_id="SCEN-1",
            turn_index=1,
            input_type="user_turn",
            input_text="Question 1",
            route="simple",
            route_source="structured_model",
            status="completed",
            assistant_message="Answer 1",
            passed=True,
            latency_ms=100,
        )
        scen1 = ScenarioExecutionResult(
            scenario_id="SCEN-1",
            name="Scenario 1",
            tags=["simple"],
            passed=True,
            turn_results=[turn1],
            total_latency_ms=100,
        )
        metadata = {
            "run_id": "test_run",
            "git_sha": "abc123",
            "git_branch": "main",
            "mode": "offline",
        }
        metrics = compute_aggregate_metrics([scen1], mode="offline", total_latency_ms=100)

        write_run_reports("test_run", run_dir, metadata, [scen1], metrics)

        assert (run_dir / "metadata.json").exists()
        assert (run_dir / "summary.json").exists()
        assert (run_dir / "failures.json").exists()
        assert (run_dir / "events.jsonl").exists()
        assert (run_dir / "turns.jsonl").exists()
        assert (run_dir / "report.md").exists()
