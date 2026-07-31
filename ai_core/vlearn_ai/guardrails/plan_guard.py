"""Plan guard validating pedagogical repair tool sequences."""

from collections.abc import Sequence

from vlearn_ai.config import get_settings
from vlearn_ai.schemas import AIStructuredOutputError

ALLOWED_REPAIR_TOOLS = {"review_concept", "give_example", "give_hint", "motivate"}


def normalize_plan_tools(
    planned_tools: Sequence[str],
    retry_count: int = 0,
) -> list[str]:
    """Normalize an LLM repair plan before enforcing final invariants."""
    if not planned_tools:
        raise AIStructuredOutputError(
            "Repair plan must contain at least one tool step."
        )

    unknown_tools = [tool for tool in planned_tools if tool not in ALLOWED_REPAIR_TOOLS]
    if unknown_tools:
        raise AIStructuredOutputError(
            f"Tool '{unknown_tools[0]}' is not an allowed repair tool. "
            f"Allowed: {ALLOWED_REPAIR_TOOLS}"
        )

    unique_tools = list(dict.fromkeys(planned_tools))
    if retry_count == 0:
        unique_tools = [tool for tool in unique_tools if tool != "motivate"]

    selected = set(unique_tools)
    selected.add("review_concept")
    canonical_order = ["motivate", "review_concept", "give_hint", "give_example"]
    normalized = [
        tool
        for tool in canonical_order
        if tool in selected and (tool != "motivate" or retry_count > 0)
    ]

    max_steps = get_settings().AI_MAX_REPAIR_TOOL_STEPS
    return normalized[:max_steps]


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

    if len(planned_tools) > settings.AI_MAX_REPAIR_TOOL_STEPS:
        raise AIStructuredOutputError(
            "Repair plan exceeds maximum allowed tool steps "
            f"({settings.AI_MAX_REPAIR_TOOL_STEPS})."
        )

    if len(planned_tools) != len(set(planned_tools)):
        raise AIStructuredOutputError("Repair plan must not contain duplicate tools.")

    if "review_concept" not in planned_tools:
        raise AIStructuredOutputError(
            "Repair plan must contain the required 'review_concept' tool."
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
