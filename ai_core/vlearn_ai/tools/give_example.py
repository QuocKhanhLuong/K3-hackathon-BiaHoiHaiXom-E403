"""Pedagogical tool 3: give_example."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.prompts.pedagogical_tools import GIVE_EXAMPLE_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, GiveExampleOutput


async def execute_give_example(
    concept: str,
    context: str,
    model: BaseChatModel,
) -> GiveExampleOutput:
    """Execute give_example tool using structured model output without secondary text fallback."""
    untrusted_payload = (
        f"Bối cảnh bài học:\n<untrusted_course_context>\n{context}\n</untrusted_course_context>\n\n"
        f"Khái niệm cần ví dụ minh họa:\n<untrusted_student_query>\n{concept}\n</untrusted_student_query>"
    )
    messages = build_trusted_messages(GIVE_EXAMPLE_PROMPT, untrusted_payload)

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(GiveExampleOutput)
            res = await structured.ainvoke(messages)
            if isinstance(res, GiveExampleOutput) and res.example.strip():
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"give_example structured output failed: {exc}"
        ) from exc

    raise AIStructuredOutputError(
        "give_example failed to produce valid GiveExampleOutput."
    )
