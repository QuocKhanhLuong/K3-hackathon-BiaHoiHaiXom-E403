"""Deterministic boundary between course evidence and model knowledge."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Answerability = Literal["course_grounded", "general_knowledge", "insufficient_context"]


@dataclass(frozen=True)
class AnswerabilityDecision:
    """Safe answer source selected before answer generation."""

    answerability: Answerability
    answerability_code: str
    source_mode: Literal["course", "model_knowledge", "none"]


@dataclass(frozen=True)
class DirectDefinitionEvidence:
    """Verbatim direct definition tied to its exact retrieved source."""

    source_id: str
    snippet: str


_SOURCE_HEADER = re.compile(
    r'^\[source\s+source_id="(?P<source_id>[^"]+)"[^\]]*\]\s*$', re.MULTILINE
)
_WORD = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
_DEFINITION = re.compile(
    r"^\s*(?:hãy\s+)?(?:giải\s+thích\s+|cho\s+(?:tôi|mình)\s+biết\s+)?"
    r"(?P<entity>.{1,100}?)\s+(?:là|la)\s+gì\s*[?？]?\s*$",
    re.IGNORECASE,
)
_COURSE_REFERENCE = re.compile(
    r"\b(?:slide|trang|page)\s*(?:này|đó|ấy|\d+)\b|"
    r"\b(?:đoạn|phần|chương)\s+(?:này|đó|ấy)\b|"
    r"\btheo\s+(?:bài|slide|trang|đoạn|thầy|cô)\b|"
    r"\btrong\s+(?:bài|khóa\s+học|giáo\s+trình)\b|"
    r"\b(?:agenda|bài\s+học|giáo\s+trình|nội\s+dung\s+bài|khóa\s+học)\b",
    re.IGNORECASE,
)
_EXACT_COURSE_FACT = re.compile(
    r"\b(?:bao\s+nhiêu|mấy|tiêu\s+đề|người\s+dạy)\b.{0,80}\b"
    r"(?:slide|trang|agenda|bài\s+học|khóa\s+học|giáo\s+trình|chương|phần)\b|"
    r"\b(?:slide|trang|page)\s*\d+\b",
    re.IGNORECASE,
)
_HIGH_RISK = re.compile(
    r"\b(?:medical|medicine|diagnos(?:is|e)|treatment|drug|dose|triệu\s+chứng|"
    r"chẩn\s+đoán|điều\s+trị|thuốc|liều\s+dùng|pháp\s+lý|luật|hợp\s+đồng|"
    r"kiện\s+tụng|đầu\s+tư|chứng\s+khoán|tài\s+chính|crypto|bảo\s+mật|"
    r"security|vulnerability|exploit|malware|hack|xâm\s+nhập)\b",
    re.IGNORECASE,
)
_NON_STANDALONE = re.compile(
    r"\b(?:kiểm\s+tra|quiz|trắc\s+nghiệm|đánh\s+giá|bài\s+tập|làm\s+bài)\b",
    re.IGNORECASE,
)
_STANDALONE_INFORMATION = re.compile(
    r"\b(?:là|la)\s+gì\b|\b(?:hoạt\s+động|vận\s+hành|khác\s+nhau)\s+"
    r"(?:như\s+thế\s+nào|ra\s+sao|thế\s+nào)\b|"
    r"\b(?:kể|cho(?:\s+(?:tôi|mình))?)(?:\s+(?:một|thêm))?\s+ví\s+dụ\b|"
    r"\b(?:mô\s+tả|giải\s+thích|tóm\s+tắt|trình\s+bày|cho\s+biết|tại\s+sao)\b|"
    r"\bcách\b|\b(?:quy\s+trình|giai\s+đoạn)\b|\bwhat\s+is\b|"
    r"\bhow\s+(?:does|do)\b|\bdifference\s+between\b",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "ai",
    "anh",
    "bạn",
    "cái",
    "cho",
    "có",
    "của",
    "gì",
    "giải",
    "hãy",
    "không",
    "là",
    "mình",
    "nào",
    "này",
    "nói",
    "sao",
    "thế",
    "tôi",
    "về",
    "và",
    "what",
    "which",
}


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _source_bodies(context: str) -> list[str]:
    """Return only source bodies, never source metadata headers."""
    headers = list(_SOURCE_HEADER.finditer(context))
    bodies: list[str] = []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(context)
        bodies.append(_normalized(context[header.end() : end]))
    return bodies


def _source_sections(context: str) -> list[tuple[str, str]]:
    """Return source IDs with their original body text for exact citations."""
    headers = list(_SOURCE_HEADER.finditer(context))
    sections: list[tuple[str, str]] = []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(context)
        sections.append(
            (header.group("source_id"), context[header.end() : end].strip())
        )
    return sections


def _keywords(query: str) -> set[str]:
    return {
        token
        for token in _WORD.findall(_normalized(query))
        if len(token) > 1 and token not in _STOP_WORDS
    }


def extract_direct_definition_evidence(
    query: str, context: str
) -> DirectDefinitionEvidence | None:
    """Find one verbatim body-level definition for a ``X là gì?`` question."""
    definition = _DEFINITION.match(query)
    if not definition:
        return None
    entity = re.escape(
        unicodedata.normalize("NFKC", definition.group("entity")).strip()
    )
    direct_pattern = re.compile(
        rf"\b{entity}\s*(?:\([^)]{{1,120}}\)\s*)?"
        rf"(?:(?:là|la)\s+|=\s*|(?:được\s+)?dùng\s+(?:để\s+)?|"
        rf"có\s+vai\s+trò\s+(?:là\s+)?|giúp\s+)(?!gì\b)[^.!?]+[.!?]?",
        re.IGNORECASE,
    )
    for source_id, body in _source_sections(context):
        match = direct_pattern.search(unicodedata.normalize("NFKC", body))
        if match:
            return DirectDefinitionEvidence(
                source_id=source_id,
                # PDF slide extraction wraps visual lines.  Grounding
                # canonicalizes whitespace too, so this remains the exact
                # source sentence while rendering naturally in the UI.
                snippet=re.sub(r"\s+", " ", match.group(0)).strip(),
            )
    return None


def has_direct_course_evidence(query: str, context: str) -> bool:
    """Detect direct answer evidence without trusting a model to self-authorize.

    Legacy hand-authored contexts lack source chunk metadata. They retain the
    established course-grounded flow because their provenance cannot be ranked
    reliably here; retrieval-generated bundles use typed headers and receive
    the stricter check below.
    """
    if context.strip() and "chunk_id=" not in context:
        return True

    bodies = _source_bodies(context)
    if not bodies:
        return bool(context.strip())

    if _DEFINITION.match(query):
        return extract_direct_definition_evidence(query, context) is not None

    keywords = _keywords(query)
    if not keywords:
        return False
    # A title-only mention is not direct evidence.  For non-definition
    # questions require at least two meaningful query terms in one body;
    # this still admits a directly described relation such as Key + Query.
    minimum_matches = min(2, len(keywords))
    return any(
        sum(bool(re.search(rf"\b{re.escape(word)}\b", body)) for word in keywords)
        >= minimum_matches
        for body in bodies
    )


def decide_answerability(query: str, context: str) -> AnswerabilityDecision:
    """Choose course, general knowledge, or abstention using safe local rules."""
    normalized_query = _normalized(query)
    if has_direct_course_evidence(query, context):
        return AnswerabilityDecision(
            "course_grounded", "course_evidence_found", "course"
        )

    if _HIGH_RISK.search(normalized_query):
        return AnswerabilityDecision(
            "insufficient_context", "general_knowledge_high_risk", "none"
        )
    if _COURSE_REFERENCE.search(normalized_query) or _EXACT_COURSE_FACT.search(
        normalized_query
    ):
        return AnswerabilityDecision(
            "insufficient_context", "course_evidence_missing", "none"
        )
    if _NON_STANDALONE.search(normalized_query) or not _STANDALONE_INFORMATION.search(
        normalized_query
    ):
        return AnswerabilityDecision(
            "insufficient_context", "general_knowledge_not_standalone", "none"
        )
    return AnswerabilityDecision(
        "general_knowledge", "general_knowledge_no_course_evidence", "model_knowledge"
    )
