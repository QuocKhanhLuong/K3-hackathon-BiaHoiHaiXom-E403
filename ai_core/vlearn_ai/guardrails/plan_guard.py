"""Plan guard validating pedagogical repair tool sequences."""

from collections.abc import Sequence

from vlearn_ai.schemas import AIStructuredOutputError

ALLOWED_REPAIR_TOOLS = {"review_concept", "give_example", "give_hint", "motivate"}
MAX_REPAIR_TOOL_STEPS = 3


def validate_plan_tools(
    planned_tools: Sequence[str],
    retry_count: int = 0,
) -> bool:
    """Validate that planned repair tools are strictly allowed and comply with retry rules."""
    if not planned_tools:
        raise AIStructuredOutputError(
            "Repair plan must contain at least one tool step."
        )

    if len(planned_tools) > MAX_REPAIR_TOOL_STEPS:
        raise AIStructuredOutputError(
            f"Repair plan exceeds maximum allowed tool steps ({MAX_REPAIR_TOOL_STEPS})."
        )

    if len(set(planned_tools)) != len(planned_tools):
        raise AIStructuredOutputError("Repair plan must not contain duplicate tools.")

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
