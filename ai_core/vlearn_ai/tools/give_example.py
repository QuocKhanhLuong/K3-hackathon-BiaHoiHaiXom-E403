"""Pedagogical tool 3: give_example."""

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from vlearn_ai.prompts.pedagogical_tools import GIVE_EXAMPLE_PROMPT


class ExampleOutput(BaseModel):
    """Output format for give_example tool."""

    example: str
    concept_mapping: str
    explanation: str
    evidence: list[str] = Field(default_factory=list)


async def execute_give_example(
    concept: str,
    context: str,
    model: BaseChatModel,
) -> ExampleOutput:
    """Generate a concrete example mapping back to concept."""
    prompt = GIVE_EXAMPLE_PROMPT.format(
        selected_context=context,
        concept=concept,
    )

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(ExampleOutput)
            res = await structured.ainvoke(prompt)
            if isinstance(res, ExampleOutput):
                return res
    except (AttributeError, ValueError, TypeError, RuntimeError):
        pass

    return ExampleOutput(
        example=f"Ví dụ minh họa cho '{concept}' trong bối cảnh bài học.",
        concept_mapping=f"Ánh xạ giữa ví dụ và khái niệm {concept}.",
        explanation="Lời giải thích ví dụ chi tiết.",
        evidence=[context[:100]] if context else [],
    )
