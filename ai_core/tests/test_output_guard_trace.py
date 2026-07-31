"""Tests for safe observability metadata in public tool traces."""

from vlearn_ai.guardrails.output_guard import sanitize_tool_trace


def test_sanitize_tool_trace_keeps_only_allowlisted_observability_details():
    sanitized = sanitize_tool_trace(
        [
            {
                "tool": "evaluate_check",
                "status": "success",
                "model": "test-model",
                "prompt_version": "1.0.0",
                "details": {
                    "check_id": "check-1",
                    "attempt_index": 2,
                    "retry_count": 1,
                    "evaluation_source": "deterministic_mcq",
                    "misconception_code": "incorrect_option",
                    "expected_answer": "private answer",
                    "raw_prompt": "private prompt",
                    "selected_context": "private context",
                },
            }
        ]
    )

    assert sanitized[0]["details"] == {
        "check_id": "check-1",
        "attempt_index": 2,
        "retry_count": 1,
        "evaluation_source": "deterministic_mcq",
        "misconception_code": "incorrect_option",
    }
