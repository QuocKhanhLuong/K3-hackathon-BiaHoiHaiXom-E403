"""Plan guard validating pedagogical tools against fixed allowlist."""

from vlearn_ai.config import get_settings

ALLOWED_PEDAGOGICAL_TOOLS = {
    "review_concept",
    "give_direct_answer",
    "give_example",
    "motivate",
    "give_hint",
    "validate_understanding",
}


def validate_plan_tools(planned_tools: list[str]) -> tuple[bool, str | None]:
    """Validate planned tools against central fixed allowlist and step count."""
    settings = get_settings()

    if len(planned_tools) > settings.AI_MAX_TOOL_STEPS:
        return (
            False,
            f"Tool step count ({len(planned_tools)}) exceeds maximum limit ({settings.AI_MAX_TOOL_STEPS}).",
        )

    for tool in planned_tools:
        if tool not in ALLOWED_PEDAGOGICAL_TOOLS:
            return (
                False,
                f"Tool '{tool}' is not in the allowed pedagogical tool registry.",
            )

    return True, None
