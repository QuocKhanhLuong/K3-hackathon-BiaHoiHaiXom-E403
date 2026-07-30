"""Context guardrail to treat course context as untrusted data."""

from typing import Any

from vlearn_ai.guardrails.input_guard import check_input_heuristics


def check_context_safety(context: str, max_chars: int = 12000) -> dict[str, Any]:
    """Check course context length and potential embedded injection patterns.

    Course material is untrusted evidence. If it contains prompt injection text,
    it may be quoted as subject matter, but must not be executed.
    """
    truncated_context = context[:max_chars]
    heuristic = check_input_heuristics(truncated_context)

    return {
        "is_safe_reference": True,
        "is_truncated": len(context) > max_chars,
        "context": truncated_context,
        "embedded_injection_detected": heuristic["is_flagged"],
        "patterns": heuristic["patterns"],
    }
