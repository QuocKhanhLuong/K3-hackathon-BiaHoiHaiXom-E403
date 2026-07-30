"""Pedagogical tool 4: give_hint."""

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from vlearn_ai.prompts.pedagogical_tools import GIVE_HINT_PROMPT


class HintOutput(BaseModel):
    """Output format for give_hint tool."""

    hint: str
    hint_level: int
    expected_next_thought: str


async def execute_give_hint(
    topic: str,
    current_state: str,
    model: BaseChatModel,
    hint_level: int = 1,
) -> HintOutput:
    """Give a progressive hint without revealing the complete answer immediately."""
    prompt = GIVE_HINT_PROMPT.format(
        topic=topic,
        current_state=current_state,
    )

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(HintOutput)
            res = await structured.ainvoke(prompt)
            if isinstance(res, HintOutput):
                return res
    except (AttributeError, ValueError, TypeError, RuntimeError):
        pass

    return HintOutput(
        hint=f"Gợi ý mức {hint_level} cho khái niệm: {topic}.",
        hint_level=hint_level,
        expected_next_thought="Hãy liên hệ khái niệm này với vai trò chính của nó.",
    )
