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


_SOURCE_HEADER = re.compile(r'^\[source\s+source_id="[^"]+"[^\]]*\]\s*$', re.MULTILINE)
_WORD = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
_DEFINITION = re.compile(
    r"^\s*(?:hãy\s+)?(?:giải\s+thích\s+|cho\s+(?:tôi|mình)\s+biết\s+)?"
    r"(?P<entity>.{1,100}?)\s+(?:là|la)\s+gì\s*[?？]?\s*$",
    re.IGNORECASE,
)
_COURSE_REFERENCE = re.compile(
    r"\b(?:slide|trang|đoạn|theo\s+(?:bài|slide|thầy|cô)|"
    r"trong\s+(?:bài|khóa\s+học)|agenda|bài\s+học|giáo\s+trình|"
    r"nội\s+dung\s+bài)\b",
    re.IGNORECASE,
)
_EXACT_COURSE_FACT = re.compile(
    r"\b(?:bao\s+nhiêu|mấy|tiêu\s+đề|bước|phần|chương|slide|trang|"
    r"agenda|người\s+dạy|thầy|cô)\b",
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
    r"(?:\b(?:là|la)\s+gì\b|\b(?:hoạt\s+động|vận\s+hành|khác\s+nhau)\s+"
    r"(?:như\s+thế\s+nào|ra\s+sao|thế\s+nào)\b|\bwhat\s+is\b|"
    r"\bhow\s+(?:does|do)\b|\bdifference\s+between\b)",
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


def _keywords(query: str) -> set[str]:
    return {
        token
        for token in _WORD.findall(_normalized(query))
        if len(token) > 1 and token not in _STOP_WORDS
    }


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

    definition = _DEFINITION.match(query)
    if definition:
        entity = re.escape(_normalized(definition.group("entity")))
        direct_pattern = re.compile(
            rf"\b{entity}\s*(?:\([^)]{{1,120}}\)\s*)?"
            rf"(?:(?:là|la)\s+|=\s*|(?:được\s+)?dùng\s+(?:để\s+)?|"
            rf"có\s+vai\s+trò\s+(?:là\s+)?|giúp\s+)(?!gì\b).+",
            re.IGNORECASE,
        )
        return any(direct_pattern.search(body) for body in bodies)

    keywords = _keywords(query)
    if not keywords:
        return False
    return any(
        any(re.search(rf"\b{re.escape(word)}\b", body) for word in keywords)
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
