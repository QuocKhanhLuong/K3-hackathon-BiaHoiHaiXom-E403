"""Pedagogical tool 5: motivate."""

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from vlearn_ai.prompts.pedagogical_tools import MOTIVATE_PROMPT


class MotivateOutput(BaseModel):
    """Output format for motivate tool."""

    message: str
    acknowledged_difficulty: str
    next_small_step: str


async def execute_motivate(
    difficulty: str,
    model: BaseChatModel,
) -> MotivateOutput:
    """Give short, specific encouragement only when there is evidence of frustration or repeated failure."""
    prompt = MOTIVATE_PROMPT.format(difficulty=difficulty)

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(MotivateOutput)
            res = await structured.ainvoke(prompt)
            if isinstance(res, MotivateOutput):
                return res
    except (AttributeError, ValueError, TypeError, RuntimeError):
        pass

    return MotivateOutput(
        message=f"Đừng lo lắng, khái niệm này khá dễ nhầm lẫn: {difficulty}. Chúng ta sẽ đi từng bước nhỏ nhé!",
        acknowledged_difficulty=difficulty,
        next_small_step="Hãy thử xem lại ví dụ ngắn sau đây.",
    )
