"""Workflow 2: Check understanding."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.schemas import MicroCheck
from vlearn_ai.tools.validate_understanding import execute_validate_understanding


async def run_check_understanding(
    context: str,
    grounded_answer: str,
    model: BaseChatModel,
    previous_check: MicroCheck | None = None,
) -> MicroCheck:
    """Run check understanding workflow in generate mode."""
    res = await execute_validate_understanding(
        mode="generate_check",
        context=context,
        grounded_answer=grounded_answer,
        model=model,
        previous_check=previous_check,
    )
    if isinstance(res, MicroCheck):
        return res
    raise ValueError("Expected MicroCheck from execute_validate_understanding.")
