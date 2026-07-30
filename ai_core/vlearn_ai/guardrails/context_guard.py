"""Context guard verifying length and detecting prompt injection patterns in course context."""

import re
from typing import Any

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"system\s+prompt\s+override",
    r"disregard\s+the\s+above",
    r"you\s+are\s+now",
    r"reveal\s+(the\s+)?hidden\s+prompt",
]


def check_context_safety(context: str, max_chars: int = 12000) -> dict[str, Any]:
    """Check course context length and flag prompt injection patterns."""
    truncated = False
    if len(context) > max_chars:
        context = context[:max_chars]
        truncated = True

    detected_patterns: list[str] = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, context, re.IGNORECASE):
            detected_patterns.append(pattern)

    return {
        "context": context,
        "context_truncated": truncated,
        "context_injection_detected": len(detected_patterns) > 0,
        "context_injection_patterns": detected_patterns,
    }
