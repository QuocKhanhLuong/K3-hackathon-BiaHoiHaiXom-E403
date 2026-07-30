"""Output guardrail for sanitizing system response."""

import re

SENSITIVE_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",
    r"OPENAI_API_KEY",
    r"SYSTEM_PROMPT_VERSION",
    r"<untrusted_student_query>",
    r"<untrusted_course_context>",
]


def sanitize_output(text: str) -> tuple[str, bool]:
    """Sanitize output text to remove prompt leaks, API keys, and script tags."""
    sanitized = text
    leak_detected = False

    # Check and remove sensitive patterns
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, sanitized):
            leak_detected = True
            sanitized = re.sub(pattern, "[REDACTED]", sanitized)

    # Sanitize HTML script tags
    if "<script" in sanitized.lower():
        leak_detected = True
        sanitized = re.sub(
            r"<script.*?>.*?</script>", "", sanitized, flags=re.DOTALL | re.IGNORECASE
        )

    return sanitized, leak_detected
