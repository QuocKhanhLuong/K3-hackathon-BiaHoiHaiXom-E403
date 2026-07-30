"""Output guard sanitizing all user-visible assistant content."""

import re
from typing import Any

SENSITIVE_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",  # API keys
    r"SYSTEM_PROMPT",
    r"GLOBAL_SYSTEM_PROMPT",
    r"ROUTER_SYSTEM_PROMPT",
    r"OPENAI_API_KEY",
    r"<untrusted_student_query>",
    r"<untrusted_course_context>",
    r"<untrusted_student_answer>",
]


def sanitize_text(text: str | None) -> tuple[str | None, bool]:
    """Sanitize text string against sensitive patterns and HTML script tags."""
    if not text:
        return text, False

    leak_detected = False

    # Remove script tags
    if "<script" in text.lower():
        text = re.sub(
            r"<script.*?>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL
        )
        text = re.sub(r"<script.*?>", "", text, flags=re.IGNORECASE)
        leak_detected = True

    # Redact sensitive internal strings
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
            leak_detected = True

    return text, leak_detected


def sanitize_output(content: str | None) -> tuple[str, bool]:
    """Sanitize grounded answer or assistant message."""
    sanitized, leak = sanitize_text(content or "")
    return sanitized or "", leak


def sanitize_all_output_fields(
    assistant_message: str | None,
    clarification_question: str | None,
    check_question: dict[str, Any] | None,
    followups: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    blocked_reason: str | None,
) -> tuple[
    str | None,
    str | None,
    dict[str, Any] | None,
    list[dict[str, Any]],
    list[dict[str, Any]],
    str | None,
]:
    """Sanitize all user-facing output fields to ensure no sensitive details or scripts leak."""
    clean_msg, _ = sanitize_text(assistant_message)
    clean_clar, _ = sanitize_text(clarification_question)
    clean_blocked, _ = sanitize_text(blocked_reason)

    clean_check: dict[str, Any] | None = None
    if check_question:
        clean_check = dict(check_question)
        clean_check["question"], _ = sanitize_text(clean_check.get("question"))
        clean_check["explanation"], _ = sanitize_text(clean_check.get("explanation"))
        if "options" in clean_check and isinstance(clean_check["options"], list):
            clean_opts = []
            for opt in clean_check["options"]:
                if isinstance(opt, dict):
                    opt_copy = dict(opt)
                    opt_copy["text"], _ = sanitize_text(opt_copy.get("text"))
                    clean_opts.append(opt_copy)
            clean_check["options"] = clean_opts

    clean_followups = []
    for f in followups:
        f_copy = dict(f)
        f_copy["label"], _ = sanitize_text(f_copy.get("label"))
        f_copy["question"], _ = sanitize_text(f_copy.get("question"))
        clean_followups.append(f_copy)

    clean_citations = []
    for c in citations:
        c_copy = dict(c)
        c_copy["snippet"], _ = sanitize_text(c_copy.get("snippet"))
        clean_citations.append(c_copy)

    return (
        clean_msg,
        clean_clar,
        clean_check,
        clean_followups,
        clean_citations,
        clean_blocked,
    )
