"""Output guard sanitizing all user-facing assistant messages and interrupt payloads."""

import re
from typing import Any


def sanitize_output(text: str | None) -> tuple[str, bool]:
    """Sanitize output text by stripping HTML script tags, prompt leak keywords, and internal XML tags."""
    if not text:
        return "", False

    original = text
    cleaned = text

    # Strip script tags and HTML elements
    cleaned = re.sub(
        r"<script.*?>.*?</script>", "", cleaned, flags=re.DOTALL | re.IGNORECASE
    )
    cleaned = re.sub(r"</?[a-z1-6]+(?:\s+[^>]*)?>", "", cleaned, flags=re.IGNORECASE)

    # Redact untrusted XML tags
    cleaned = re.sub(r"</?untrusted_[a-z_]+>", "", cleaned, flags=re.IGNORECASE)

    # Redact sensitive prompt/API key terms
    leak_patterns = [
        r"sk-[a-zA-Z0-9]{20,}",
        r"GLOBAL_SYSTEM_PROMPT",
        r"SYSTEM_PROMPT",
        r"ROUTER_SYSTEM_PROMPT",
        r"with_structured_output",
    ]

    has_leak = False
    for pat in leak_patterns:
        if re.search(pat, cleaned, flags=re.IGNORECASE):
            has_leak = True
            cleaned = re.sub(pat, "[REDACTED]", cleaned, flags=re.IGNORECASE)

    return cleaned.strip(), has_leak or (cleaned != original)


def sanitize_all_output_fields(
    assistant_message: str | None = None,
    clarification_question: str | None = None,
    check_question: dict[str, Any] | None = None,
    followups: list[dict[str, Any]] | None = None,
    citations: list[dict[str, Any]] | None = None,
    blocked_reason: str | None = None,
) -> tuple[
    str,
    str | None,
    dict[str, Any] | None,
    list[dict[str, Any]],
    list[dict[str, Any]],
    str | None,
]:
    """Sanitize all user-facing output fields."""
    clean_msg, _ = sanitize_output(assistant_message)
    clean_clar, _ = (
        sanitize_output(clarification_question)
        if clarification_question
        else (None, False)
    )

    clean_check = None
    if check_question and isinstance(check_question, dict):
        clean_check = dict(check_question)
        if clean_check.get("question"):
            clean_check["question"], _ = sanitize_output(str(clean_check["question"]))
        if clean_check.get("explanation"):
            clean_check["explanation"], _ = sanitize_output(
                str(clean_check["explanation"])
            )
        if clean_check.get("options") and isinstance(clean_check["options"], list):
            clean_opts = []
            for opt in clean_check["options"]:
                if isinstance(opt, dict):
                    c_opt = dict(opt)
                    c_opt["text"], _ = sanitize_output(str(c_opt.get("text", "")))
                    clean_opts.append(c_opt)
            clean_check["options"] = clean_opts

    clean_followups = []
    if followups:
        for f in followups:
            if isinstance(f, dict):
                c_f = dict(f)
                c_f["label"], _ = sanitize_output(str(c_f.get("label", "")))
                c_f["question"], _ = sanitize_output(str(c_f.get("question", "")))
                clean_followups.append(c_f)

    clean_citations = []
    if citations:
        for c in citations:
            if isinstance(c, dict):
                c_c = dict(c)
                c_c["snippet"], _ = sanitize_output(str(c_c.get("snippet", "")))
                clean_citations.append(c_c)

    clean_blocked, _ = (
        sanitize_output(blocked_reason) if blocked_reason else (None, False)
    )

    return (
        clean_msg,
        clean_clar,
        clean_check,
        clean_followups,
        clean_citations,
        clean_blocked,
    )


def sanitize_tool_trace(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitize tool execution trace to prevent leaking internal prompts or raw tool arguments."""
    safe_detail_fields = {
        "check_id",
        "attempt_index",
        "retry_count",
        "evaluation_source",
        "misconception_code",
        "repair_tools",
        "previous_check_id",
    }
    safe_trace = []
    for item in trace:
        if isinstance(item, dict):
            safe_item = {
                "tool": item.get("tool", "unknown"),
                "status": item.get("status", "success"),
                "model": item.get("model", "gpt-5-nano"),
                "prompt_version": item.get("prompt_version", "1.0.0"),
            }
            raw_details = item.get("details")
            if isinstance(raw_details, dict):
                safe_details = {
                    key: value
                    for key, value in raw_details.items()
                    if key in safe_detail_fields
                }
                if safe_details:
                    safe_item["details"] = safe_details
            safe_trace.append(safe_item)
    return safe_trace
