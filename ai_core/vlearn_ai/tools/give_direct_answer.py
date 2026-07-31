"""Pedagogical tool 2: give_direct_answer."""

import re
import unicodedata

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.prompts.pedagogical_tools import GIVE_DIRECT_ANSWER_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, GroundedAnswer


def _has_direct_definition_evidence(query: str, context: str) -> bool | None:
    """Return False only for a RAG bundle that lacks a body-level definition.

    Hand-authored legacy contexts do not include a ``chunk_id`` and retain
    their historical model path.  Retrieval-generated bundles are explicit
    enough to make insufficiency a deterministic, non-model outcome.
    """
    match = re.search(
        r"^\s*(.{1,80}?)\s+(?:là|la)\s+gì\s*[?？]?$", query, re.IGNORECASE
    )
    if not match:
        return None
    entity = unicodedata.normalize("NFKC", match.group(1)).casefold().strip()
    source_headers = list(
        re.finditer(
            r'^\[source\s+source_id="[^"]+"\s+chunk_id="[^"]+"[^\]]*\]\s*$',
            context,
            re.MULTILINE,
        )
    )
    if not source_headers:
        return None
    direct = re.compile(
        rf"\b{re.escape(entity)}\s*(?:\([^)]{{1,120}}\)\s*)?"
        rf"(?:(?:là|la)\s+|=\s*|(?:được\s+)?dùng\s+(?:để\s+)?|"
        rf"có\s+vai\s+trò\s+(?:là\s+)?|giúp\s+)(?!gì\b).+",
        re.IGNORECASE,
    )
    for index, header in enumerate(source_headers):
        end = (
            source_headers[index + 1].start()
            if index + 1 < len(source_headers)
            else len(context)
        )
        source_body = unicodedata.normalize(
            "NFKC", context[header.end() : end]
        ).casefold()
        if direct.search(source_body):
            return True
    return False


async def execute_give_direct_answer(
    query: str,
    context: str,
    model: BaseChatModel,
) -> GroundedAnswer:
    """Execute give_direct_answer tool using structured model output without secondary text fallback."""
    if _has_direct_definition_evidence(query, context) is False:
        return GroundedAnswer(
            answer=(
                "Ngữ cảnh bài học đã truy xuất chưa có định nghĩa trực tiếp "
                "cho khái niệm này."
            ),
            answerability="insufficient_context",
            answerability_code="definition_evidence_missing",
            claims=[],
            citations=[],
        )
    untrusted_payload = (
        f"Bối cảnh bài học:\n<untrusted_course_context>\n{context}\n</untrusted_course_context>\n\n"
        f"Câu hỏi sự thật:\n<untrusted_student_query>\n{query}\n</untrusted_student_query>"
    )
    messages = build_trusted_messages(GIVE_DIRECT_ANSWER_PROMPT, untrusted_payload)

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(GroundedAnswer)
            res = await structured.ainvoke(messages)
            if isinstance(res, GroundedAnswer) and res.answer.strip():
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"give_direct_answer structured output failed: {exc}"
        ) from exc

    raise AIStructuredOutputError(
        "give_direct_answer failed to produce valid GroundedAnswer."
    )
