"""Plan guardrail with fixed tool allowlist registry."""

ALLOWED_TOOLS: set[str] = {
    "review_concept",
    "give_direct_answer",
    "give_example",
    "motivate",
    "give_hint",
    "validate_understanding",
}


def validate_tool_name(tool_name: str) -> bool:
    """Check if tool_name is in the explicit allowlist."""
    return tool_name in ALLOWED_TOOLS


def validate_plan_steps(
    tool_sequence: list[str],
    max_steps: int = 4,
) -> tuple[bool, str | None]:
    """Validate a sequence of tool steps against length limits and allowlist."""
    if len(tool_sequence) > max_steps:
        return (
            False,
            f"Plan exceeds maximum tool steps limit ({len(tool_sequence)} > {max_steps})",
        )

    for tool in tool_sequence:
        if not validate_tool_name(tool):
            return False, f"Disallowed or unknown tool requested: '{tool}'"

    return True, None
