"""Plan guard validating pedagogical repair tool sequences."""

from collections.abc import Sequence

from vlearn_ai.config import get_settings
from vlearn_ai.schemas import AIStructuredOutputError

ALLOWED_REPAIR_TOOLS = {"review_concept", "give_example", "give_hint", "motivate"}


def validate_plan_tools(
    planned_tools: Sequence[str],
    retry_count: int = 0,
) -> bool:
    """Validate that planned repair tools are strictly allowed and comply with retry rules."""
    settings = get_settings()

    if not planned_tools:
        raise AIStructuredOutputError(
            "Repair plan must contain at least one tool step."
        )

    if len(planned_tools) > settings.AI_MAX_TOOL_STEPS:
        raise AIStructuredOutputError(
            f"Repair plan exceeds maximum allowed tool steps ({settings.AI_MAX_TOOL_STEPS})."
        )

    for tool in planned_tools:
        if tool not in ALLOWED_REPAIR_TOOLS:
            raise AIStructuredOutputError(
                f"Tool '{tool}' is not an allowed repair tool. Allowed: {ALLOWED_REPAIR_TOOLS}"
            )

        if tool == "motivate" and retry_count == 0:
            raise AIStructuredOutputError(
                "Tool 'motivate' is not allowed on the first normal mistake (retry_count == 0)."
            )

    return True
