#!/usr/bin/env python3
"""EDA toàn diện cho VLearn Hackathon chatlog.

Mục tiêu
--------
1. Kiểm tra chất lượng dữ liệu và ghép mỗi lượt hỏi-đáp theo ``turn_id``.
2. Phân tích hành vi sư phạm, citation, learning loop, rating, latency và token.
3. Tìm các pain point tiềm năng từ dữ liệu ở cấp turn, conversation và user.
4. Lấy ví dụ nguyên văn ẩn danh, tạo mẫu annotation để review thủ công.
5. Sinh báo cáo Markdown và biểu đồ dùng trực tiếp cho Checkpoint 1.

Script chạy hoàn toàn local, không gọi API và không upload dữ liệu.
Không commit raw CSV hoặc thư mục output chứa nội dung nguyên văn lên public repo.

Cài đặt
-------
pip install pandas numpy matplotlib

Chạy
----
python vlearn_eda.py \
  --input data/vlearn-pack/chatlog/chat_history_anonymized_for_hackathon.csv \
  --output-dir eda_output

Output chính
------------
eda_output/
├── EDA_REPORT.md
├── CP1_DRAFT.md
├── metrics.json
├── turn_level_analysis.csv
├── conversation_level_analysis.csv
├── annotation_sample.csv
├── evidence_examples.csv
└── figures/
    ├── 01_move_distribution.png
    ├── 02_learning_loop_and_grounding.png
    ├── 03_latency_distribution.png
    ├── 04_answer_length_by_move.png
    ├── 05_conversation_turns.png
    └── 06_rating_slices.png
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import re
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Cấu hình và heuristic
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = {
    "conversation_id",
    "user_id",
    "day_code",
    "turn_id",
    "role",
    "content",
    "move_used",
    "citations",
    "misconceptions",
    "follow_ups",
    "rating",
    "asked_check_question",
    "message_created_at",
    "llm_call_count",
    "models_used",
    "total_input_tokens",
    "total_output_tokens",
    "total_cost_usd",
    "avg_latency_ms",
}

PAGE_CONTEXT_RE = re.compile(
    r"\(?\s*Trang\s+(?P<page>\d+)\s*,\s*đoạn được chọn:\s*[\"“](?P<selection>.*?)[\"”]\s*\)?",
    flags=re.IGNORECASE | re.DOTALL,
)

VAGUE_RE = re.compile(
    r"\b(?:cái này|đoạn này|phần này|ý này|chỗ này|ở trên|đoạn trên|"
    r"này là gì|là sao|giải thích thêm|không hiểu|chưa hiểu)\b",
    flags=re.IGNORECASE,
)

EXAMPLE_REQUEST_RE = re.compile(
    r"\b(?:ví dụ|minh họa|minh hoạ|example|case study|thực tế)\b",
    flags=re.IGNORECASE,
)

SUMMARY_REQUEST_RE = re.compile(
    r"\b(?:tóm tắt|tóm gọn|tổng hợp|ý chính|summary|summarize)\b",
    flags=re.IGNORECASE,
)

PRACTICE_REQUEST_RE = re.compile(
    r"\b(?:quiz|trắc nghiệm|câu hỏi kiểm tra|bài tập|ôn tập|flashcard|kiểm tra tôi)\b",
    flags=re.IGNORECASE,
)

LOGISTICS_RE = re.compile(
    r"\b(?:deadline|hạn nộp|nộp bài|link|đường dẫn|lịch học|phòng học|"
    r"điểm danh|mã lớp|mấy giờ|ngày mai|hôm nay|kahoot|zoom|meet|"
    r"full màn|toàn màn hình|phóng to slide)\b",
    flags=re.IGNORECASE,
)

CHECK_QUESTION_RE = re.compile(
    r"(?:theo bạn|bạn thử|bạn hãy|bạn có thể cho biết|bạn hiểu|"
    r"để kiểm tra|câu hỏi nhỏ|thử trả lời|hãy chọn|đâu là|đúng hay sai)",
    flags=re.IGNORECASE,
)

ABSTAIN_OR_CLARIFY_RE = re.compile(
    r"(?:không tìm thấy|chưa tìm thấy|không đủ (?:thông tin|căn cứ)|"
    r"chưa thể xác nhận|cần thêm (?:thông tin|ngữ cảnh)|"
    r"bạn có thể cung cấp thêm|ngoài phạm vi)",
    flags=re.IGNORECASE,
)

DIRECT_ANSWER_REQUEST_RE = re.compile(
    r"\b(?:đáp án|trả lời luôn|cho kết quả|kết quả là gì|đáp số)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class PainCandidate:
    """Một pain candidate định lượng để đưa vào impact table."""

    key: str
    title: str
    affected_turns: int
    total_turns: int
    affected_turn_pct: float
    affected_users: int
    total_users: int
    affected_user_pct: float
    affected_conversations: int
    total_conversations: int
    affected_conversation_pct: float
    evidence_definition: str
    likely_consequence: str
    caveat: str


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EDA VLearn chatlog và sinh insight CP1")
    parser.add_argument("--input", type=Path, required=True, help="Đường dẫn CSV chatlog")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("eda_output"),
        help="Thư mục lưu report và biểu đồ",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=100,
        help="Số turn đưa vào annotation_sample.csv",
    )
    parser.add_argument(
        "--examples-per-pain",
        type=int,
        default=5,
        help="Số ví dụ nguyên văn cho mỗi pain",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def pct(numerator: float | int, denominator: float | int) -> float:
    return round(100.0 * float(numerator) / float(denominator), 2) if denominator else 0.0


def parse_jsonish(value: Any) -> list[Any] | dict[str, Any] | str:
    """Parse JSON/chuỗi Python-like; lỗi thì trả về chuỗi gốc."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if isinstance(value, (list, dict)):
        return value

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return []

    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(text)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            pass
    return text


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def normalize_rating(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"up", "thumb_up", "positive", "1", "true"}:
        return "up"
    if text in {"down", "thumb_down", "negative", "-1", "false"}:
        return "down"
    return "unrated"


def normalize_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def markdown_escape(value: Any, max_chars: int = 260) -> str:
    text = normalize_text(value).replace("|", "\\|")
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


def value_count_table(series: pd.Series, total: int, name: str) -> pd.DataFrame:
    counts = series.fillna("(missing)").astype(str).value_counts(dropna=False)
    return pd.DataFrame(
        {
            name: counts.index,
            "count": counts.values,
            "rate_pct": [pct(v, total) for v in counts.values],
        }
    )


def safe_quantile(series: pd.Series, q: float) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return round(float(values.quantile(q)), 2) if not values.empty else None


def safe_mean(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return round(float(values.mean()), 2) if not values.empty else None


def json_dump(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_count(value: Any) -> int:
    parsed = parse_jsonish(value)
    if isinstance(parsed, (list, dict)):
        return len(parsed)
    return int(bool(parsed))


def extract_page_context(question: str) -> tuple[int | None, str]:
    match = PAGE_CONTEXT_RE.search(question)
    if not match:
        return None, ""
    return int(match.group("page")), normalize_text(match.group("selection"))


def strip_page_wrapper(question: str) -> str:
    """Giữ lại câu hỏi thực, loại bớt wrapper '(Trang..., đoạn được chọn...)'."""
    cleaned = PAGE_CONTEXT_RE.sub("", question)
    return normalize_text(cleaned)


# ---------------------------------------------------------------------------
# Load, validate, transform
# ---------------------------------------------------------------------------


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")

    df = pd.read_csv(path, low_memory=False)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV thiếu các cột bắt buộc: {sorted(missing)}")

    df["role"] = df["role"].astype(str).str.lower().str.strip()
    df["message_created_at"] = pd.to_datetime(df["message_created_at"], errors="coerce", utc=True)

    numeric_cols = [
        "llm_call_count",
        "total_input_tokens",
        "total_output_tokens",
        "total_cost_usd",
        "avg_latency_ms",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def validate_data(df: pd.DataFrame) -> dict[str, Any]:
    role_counts = df["role"].value_counts().to_dict()
    turn_role_counts = df.groupby(["turn_id", "role"]).size().unstack(fill_value=0)

    complete_pair_mask = (
        turn_role_counts.get("student", pd.Series(0, index=turn_role_counts.index)).eq(1)
        & turn_role_counts.get("tutor", pd.Series(0, index=turn_role_counts.index)).eq(1)
    )

    duplicates = int(df.duplicated(subset=["message_id"]).sum())
    duplicated_turn_role = int(df.duplicated(subset=["turn_id", "role"]).sum())

    return {
        "raw_rows": int(len(df)),
        "unique_messages": int(df["message_id"].nunique(dropna=True)),
        "unique_turns": int(df["turn_id"].nunique(dropna=True)),
        "complete_turn_pairs": int(complete_pair_mask.sum()),
        "incomplete_or_duplicate_turns": int((~complete_pair_mask).sum()),
        "users": int(df["user_id"].nunique(dropna=True)),
        "conversations": int(df["conversation_id"].nunique(dropna=True)),
        "day_codes": int(df["day_code"].nunique(dropna=True)),
        "role_counts": {str(k): int(v) for k, v in role_counts.items()},
        "duplicate_message_ids": duplicates,
        "duplicated_turn_role_rows": duplicated_turn_role,
        "missingness_pct": {
            col: pct(df[col].isna().sum(), len(df)) for col in df.columns
        },
    }


def build_turn_table(df: pd.DataFrame) -> pd.DataFrame:
    """Chuyển dữ liệu message-level thành một dòng cho mỗi cặp student–tutor."""
    rows: list[dict[str, Any]] = []

    for turn_id, group in df.groupby("turn_id", sort=False):
        student_rows = group[group["role"].eq("student")]
        tutor_rows = group[group["role"].eq("tutor")]
        if len(student_rows) != 1 or len(tutor_rows) != 1:
            continue

        student = student_rows.iloc[0]
        tutor = tutor_rows.iloc[0]
        question_raw = normalize_text(student["content"])
        answer = normalize_text(tutor["content"])
        selected_page, selected_text = extract_page_context(question_raw)
        question = strip_page_wrapper(question_raw) or selected_text or question_raw

        citations = parse_jsonish(tutor["citations"])
        misconceptions = parse_jsonish(tutor["misconceptions"])
        follow_ups = parse_jsonish(tutor["follow_ups"])

        question_words = len(question.split())
        answer_words = len(answer.split())
        has_check_question = (
            normalize_bool(tutor["asked_check_question"])
            or bool(CHECK_QUESTION_RE.search(answer))
            or answer.rstrip().endswith("?")
        )

        rows.append(
            {
                "turn_id": str(turn_id),
                "conversation_id": str(student["conversation_id"]),
                "user_id": str(student["user_id"]),
                "day_code": str(student["day_code"]),
                "message_created_at": tutor["message_created_at"],
                "selected_page": selected_page,
                "selected_text": selected_text,
                "question_raw": question_raw,
                "question": question,
                "answer": answer,
                "move_used": normalize_text(tutor["move_used"]) or "(missing)",
                "citations": citations,
                "citation_count": list_count(tutor["citations"]),
                "has_citation": list_count(tutor["citations"]) > 0,
                "misconceptions": misconceptions,
                "misconception_count": list_count(tutor["misconceptions"]),
                "follow_ups": follow_ups,
                "follow_up_count": list_count(tutor["follow_ups"]),
                "rating": normalize_rating(tutor["rating"]),
                "asked_check_question_field": normalize_bool(tutor["asked_check_question"]),
                "has_detected_check_question": has_check_question,
                "llm_call_count": tutor["llm_call_count"],
                "models_used": normalize_text(tutor["models_used"]),
                "total_input_tokens": tutor["total_input_tokens"],
                "total_output_tokens": tutor["total_output_tokens"],
                "total_cost_usd": tutor["total_cost_usd"],
                "avg_latency_ms": tutor["avg_latency_ms"],
                "question_words": question_words,
                "answer_words": answer_words,
                "answer_to_question_ratio": answer_words / max(question_words, 1),
                "is_vague_question": bool(VAGUE_RE.search(question)) or question_words <= 3,
                "asks_for_example": bool(EXAMPLE_REQUEST_RE.search(question)),
                "asks_for_summary": bool(SUMMARY_REQUEST_RE.search(question)),
                "asks_for_practice": bool(PRACTICE_REQUEST_RE.search(question)),
                "asks_direct_answer": bool(DIRECT_ANSWER_REQUEST_RE.search(question)),
                "is_logistics_or_ui": bool(LOGISTICS_RE.search(question)),
                "answer_abstains_or_clarifies": bool(ABSTAIN_OR_CLARIFY_RE.search(answer)),
                "likely_overlong": answer_words >= 250
                or (question_words <= 12 and answer_words >= 180),
            }
        )

    turns = pd.DataFrame(rows)
    if turns.empty:
        raise ValueError("Không tìm thấy cặp student–tutor hợp lệ theo turn_id.")

    turns = turns.sort_values(
        ["conversation_id", "message_created_at", "turn_id"],
        kind="stable",
    ).reset_index(drop=True)

    # Signal theo chuỗi hội thoại: tutor có lặp cùng move liên tiếp hay không.
    turns["previous_move"] = turns.groupby("conversation_id")["move_used"].shift(1)
    turns["same_move_as_previous"] = turns["move_used"].eq(turns["previous_move"])
    turns["repeated_review_concept"] = (
        turns["move_used"].eq("review_concept")
        & turns["previous_move"].eq("review_concept")
    )

    turns["latency_s"] = turns["avg_latency_ms"] / 1000.0
    turns["is_latency_p90_plus"] = turns["avg_latency_ms"] >= turns["avg_latency_ms"].quantile(0.90)
    turns["is_latency_p95_plus"] = turns["avg_latency_ms"] >= turns["avg_latency_ms"].quantile(0.95)
    return turns


def build_conversation_table(turns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for conversation_id, group in turns.groupby("conversation_id", sort=False):
        move_counts = group["move_used"].value_counts()
        review_count = int(move_counts.get("review_concept", 0))
        rows.append(
            {
                "conversation_id": conversation_id,
                "user_id": group["user_id"].iloc[0],
                "day_code": group["day_code"].iloc[0],
                "turn_count": int(len(group)),
                "distinct_moves": int(group["move_used"].nunique()),
                "review_concept_count": review_count,
                "review_concept_rate": review_count / len(group),
                "all_moves_are_review_concept": bool(review_count == len(group)),
                "has_repeated_review_concept": bool(group["repeated_review_concept"].any()),
                "has_any_check_question": bool(group["has_detected_check_question"].any()),
                "has_any_citation": bool(group["has_citation"].any()),
                "has_any_misconception": bool((group["misconception_count"] > 0).any()),
                "has_any_follow_up": bool((group["follow_up_count"] > 0).any()),
                "has_down_rating": bool(group["rating"].eq("down").any()),
                "avg_latency_ms": safe_mean(group["avg_latency_ms"]),
                "median_answer_words": safe_quantile(group["answer_words"], 0.5),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Metrics và insight
# ---------------------------------------------------------------------------


def impact_from_mask(
    turns: pd.DataFrame,
    mask: pd.Series,
    *,
    key: str,
    title: str,
    evidence_definition: str,
    likely_consequence: str,
    caveat: str,
) -> PainCandidate:
    affected = turns[mask.fillna(False)]
    return PainCandidate(
        key=key,
        title=title,
        affected_turns=int(len(affected)),
        total_turns=int(len(turns)),
        affected_turn_pct=pct(len(affected), len(turns)),
        affected_users=int(affected["user_id"].nunique()),
        total_users=int(turns["user_id"].nunique()),
        affected_user_pct=pct(affected["user_id"].nunique(), turns["user_id"].nunique()),
        affected_conversations=int(affected["conversation_id"].nunique()),
        total_conversations=int(turns["conversation_id"].nunique()),
        affected_conversation_pct=pct(
            affected["conversation_id"].nunique(), turns["conversation_id"].nunique()
        ),
        evidence_definition=evidence_definition,
        likely_consequence=likely_consequence,
        caveat=caveat,
    )


def build_pain_candidates(turns: pd.DataFrame) -> list[PainCandidate]:
    return [
        impact_from_mask(
            turns,
            ~turns["has_detected_check_question"],
            key="missing_learning_loop",
            title="Tutor trả lời nhưng chưa đóng vòng kiểm tra hiểu bài",
            evidence_definition=(
                "Turn không có asked_check_question=True, không khớp mẫu hỏi kiểm tra "
                "và không kết thúc bằng câu hỏi."
            ),
            likely_consequence=(
                "Học viên khó biết mình đã hiểu đúng; tutor thiếu tín hiệu để điều chỉnh lượt sau."
            ),
            caveat="Heuristic có thể bỏ sót câu kiểm tra được diễn đạt không theo mẫu.",
        ),
        impact_from_mask(
            turns,
            turns["move_used"].eq("review_concept"),
            key="low_pedagogy_diversity",
            title="Hành vi sư phạm tập trung quá mạnh vào giải thích lại",
            evidence_definition="move_used = review_concept.",
            likely_consequence=(
                "Các nhu cầu khác nhau như hint, example, sửa misconception hoặc validation "
                "có nguy cơ nhận cùng một kiểu hỗ trợ."
            ),
            caveat="move_used phản ánh label hệ thống; cần đọc mẫu để xác nhận chất lượng thực tế.",
        ),
        impact_from_mask(
            turns,
            turns["repeated_review_concept"],
            key="no_strategy_change",
            title="Tutor tiếp tục dùng review_concept ở các lượt liên tiếp",
            evidence_definition=(
                "Trong cùng conversation, lượt hiện tại và lượt trước đều có move_used=review_concept."
            ),
            likely_consequence=(
                "Khi học viên hỏi tiếp, tutor có thể chưa đổi chiến lược dù giải thích trước chưa đủ."
            ),
            caveat="Không phải mọi câu hỏi tiếp theo đều là dấu hiệu chưa hiểu; cần annotation thủ công.",
        ),
        impact_from_mask(
            turns,
            ~turns["has_citation"],
            key="missing_grounding",
            title="Câu trả lời không có citation để học viên kiểm chứng",
            evidence_definition="citations rỗng hoặc không parse được thành danh sách có phần tử.",
            likely_consequence="Học viên khó đối chiếu với tài liệu và khó biết khi nào nên tin câu trả lời.",
            caveat="Một số câu chào hỏi hoặc thao tác UI không nhất thiết cần citation.",
        ),
        impact_from_mask(
            turns,
            turns["is_latency_p90_plus"],
            key="high_latency",
            title="Một nhóm lượt phản hồi có latency cao",
            evidence_definition="avg_latency_ms nằm trong 10% cao nhất của dataset.",
            likely_consequence="Làm đứt mạch tự học và giảm khả năng học viên tiếp tục tương tác.",
            caveat="Cần log theo từng node/API call để tìm nguyên nhân; hiện mới có latency trung bình turn.",
        ),
    ]


def build_metrics(
    raw: pd.DataFrame,
    quality: dict[str, Any],
    turns: pd.DataFrame,
    conversations: pd.DataFrame,
    pains: list[PainCandidate],
) -> dict[str, Any]:
    rated = turns[turns["rating"].isin(["up", "down"])]
    move_counts = turns["move_used"].value_counts().to_dict()

    metrics: dict[str, Any] = {
        "data_quality": quality,
        "overview": {
            "turns": int(len(turns)),
            "users": int(turns["user_id"].nunique()),
            "conversations": int(turns["conversation_id"].nunique()),
            "date_min": str(turns["message_created_at"].min()),
            "date_max": str(turns["message_created_at"].max()),
            "turns_per_user_mean": safe_mean(turns.groupby("user_id").size()),
            "turns_per_conversation_mean": safe_mean(conversations["turn_count"]),
            "multi_turn_conversations": int((conversations["turn_count"] >= 2).sum()),
            "multi_turn_conversation_pct": pct(
                (conversations["turn_count"] >= 2).sum(), len(conversations)
            ),
        },
        "pedagogy": {
            "move_counts": {str(k): int(v) for k, v in move_counts.items()},
            "move_rates_pct": {str(k): pct(v, len(turns)) for k, v in move_counts.items()},
            "distinct_moves": int(turns["move_used"].nunique()),
            "review_concept_count": int(turns["move_used"].eq("review_concept").sum()),
            "review_concept_pct": pct(turns["move_used"].eq("review_concept").sum(), len(turns)),
            "repeated_review_concept_count": int(turns["repeated_review_concept"].sum()),
            "repeated_review_concept_pct": pct(turns["repeated_review_concept"].sum(), len(turns)),
            "conversations_all_review_concept": int(conversations["all_moves_are_review_concept"].sum()),
            "conversations_all_review_concept_pct": pct(
                conversations["all_moves_are_review_concept"].sum(), len(conversations)
            ),
        },
        "learning_loop": {
            "check_question_count": int(turns["has_detected_check_question"].sum()),
            "check_question_pct": pct(turns["has_detected_check_question"].sum(), len(turns)),
            "check_question_field_true": int(turns["asked_check_question_field"].sum()),
            "misconception_nonempty": int((turns["misconception_count"] > 0).sum()),
            "misconception_nonempty_pct": pct((turns["misconception_count"] > 0).sum(), len(turns)),
            "follow_up_nonempty": int((turns["follow_up_count"] > 0).sum()),
            "follow_up_nonempty_pct": pct((turns["follow_up_count"] > 0).sum(), len(turns)),
        },
        "grounding": {
            "with_citation": int(turns["has_citation"].sum()),
            "with_citation_pct": pct(turns["has_citation"].sum(), len(turns)),
            "without_citation": int((~turns["has_citation"]).sum()),
            "without_citation_pct": pct((~turns["has_citation"]).sum(), len(turns)),
            "citation_count_mean": safe_mean(turns["citation_count"]),
        },
        "feedback": {
            "rated_count": int(len(rated)),
            "rated_pct": pct(len(rated), len(turns)),
            "up_count": int(rated["rating"].eq("up").sum()),
            "down_count": int(rated["rating"].eq("down").sum()),
            "down_among_rated_pct": pct(rated["rating"].eq("down").sum(), len(rated)),
        },
        "performance": {
            "latency_ms_mean": safe_mean(turns["avg_latency_ms"]),
            "latency_ms_median": safe_quantile(turns["avg_latency_ms"], 0.5),
            "latency_ms_p90": safe_quantile(turns["avg_latency_ms"], 0.9),
            "latency_ms_p95": safe_quantile(turns["avg_latency_ms"], 0.95),
            "latency_ms_max": safe_quantile(turns["avg_latency_ms"], 1.0),
            "llm_call_count_mean": safe_mean(turns["llm_call_count"]),
            "input_tokens_mean": safe_mean(turns["total_input_tokens"]),
            "output_tokens_mean": safe_mean(turns["total_output_tokens"]),
            "answer_words_median": safe_quantile(turns["answer_words"], 0.5),
            "answer_words_p90": safe_quantile(turns["answer_words"], 0.9),
        },
        "input_patterns": {
            "vague_questions": int(turns["is_vague_question"].sum()),
            "vague_question_pct": pct(turns["is_vague_question"].sum(), len(turns)),
            "example_requests": int(turns["asks_for_example"].sum()),
            "summary_requests": int(turns["asks_for_summary"].sum()),
            "practice_requests": int(turns["asks_for_practice"].sum()),
            "logistics_or_ui": int(turns["is_logistics_or_ui"].sum()),
        },
        "pain_candidates": [asdict(pain) for pain in pains],
    }

    # Rating slices chỉ mang tính exploratory vì tỷ lệ rating rất thấp.
    for slice_name, mask in {
        "citation_present": turns["has_citation"],
        "citation_missing": ~turns["has_citation"],
        "check_present": turns["has_detected_check_question"],
        "check_missing": ~turns["has_detected_check_question"],
        "review_concept": turns["move_used"].eq("review_concept"),
        "other_moves": ~turns["move_used"].eq("review_concept"),
    }.items():
        subset = turns[mask & turns["rating"].isin(["up", "down"])]
        metrics["feedback"][f"slice_{slice_name}"] = {
            "rated_n": int(len(subset)),
            "down_n": int(subset["rating"].eq("down").sum()),
            "down_pct": pct(subset["rating"].eq("down").sum(), len(subset)),
        }

    return metrics


# ---------------------------------------------------------------------------
# Evidence sampling và annotation
# ---------------------------------------------------------------------------


def stratified_annotation_sample(
    turns: pd.DataFrame,
    sample_size: int,
    seed: int,
) -> pd.DataFrame:
    """Lấy mẫu ưu tiên hard cases, down-rating và multi-turn adaptation."""
    rng = np.random.default_rng(seed)
    strata: list[tuple[str, pd.Series, float]] = [
        ("down_rating", turns["rating"].eq("down"), 0.15),
        ("repeated_review", turns["repeated_review_concept"], 0.20),
        ("missing_citation", ~turns["has_citation"], 0.15),
        ("vague", turns["is_vague_question"], 0.15),
        ("high_latency", turns["is_latency_p95_plus"], 0.10),
        ("rare_move", ~turns["move_used"].isin(["review_concept", "give_direct_answer"]), 0.10),
        ("normal", pd.Series(True, index=turns.index), 0.15),
    ]

    selected_indices: list[int] = []
    labels: dict[int, set[str]] = {}

    for stratum, mask, proportion in strata:
        candidates = turns.index[mask & ~turns.index.isin(selected_indices)].to_numpy()
        n = min(len(candidates), max(1, round(sample_size * proportion)))
        if n <= 0:
            continue
        chosen = rng.choice(candidates, size=n, replace=False)
        for idx in chosen.tolist():
            selected_indices.append(int(idx))
            labels.setdefault(int(idx), set()).add(stratum)

    if len(selected_indices) < min(sample_size, len(turns)):
        remaining = turns.index[~turns.index.isin(selected_indices)].to_numpy()
        n = min(sample_size - len(selected_indices), len(remaining))
        if n > 0:
            chosen = rng.choice(remaining, size=n, replace=False)
            for idx in chosen.tolist():
                selected_indices.append(int(idx))
                labels.setdefault(int(idx), set()).add("fill")

    sample = turns.loc[selected_indices].copy()
    sample["sampling_reason"] = [", ".join(sorted(labels.get(int(i), {"fill"}))) for i in sample.index]

    annotation_cols = [
        "turn_id",
        "conversation_id",
        "user_id",
        "day_code",
        "question",
        "answer",
        "move_used",
        "citations",
        "rating",
        "sampling_reason",
    ]
    sample = sample[annotation_cols]
    sample["human_question_intent"] = ""
    sample["human_answer_correct"] = ""
    sample["human_citation_valid"] = ""
    sample["human_adapted_to_context"] = ""
    sample["human_detected_misconception"] = ""
    sample["human_should_check_understanding"] = ""
    sample["human_best_pedagogical_move"] = ""
    sample["human_failure_note"] = ""
    return sample


def sample_evidence(
    turns: pd.DataFrame,
    pains: Iterable[PainCandidate],
    n: int,
    seed: int,
) -> pd.DataFrame:
    masks = {
        "missing_learning_loop": ~turns["has_detected_check_question"],
        "low_pedagogy_diversity": turns["move_used"].eq("review_concept"),
        "no_strategy_change": turns["repeated_review_concept"],
        "missing_grounding": ~turns["has_citation"],
        "high_latency": turns["is_latency_p90_plus"],
    }

    frames: list[pd.DataFrame] = []
    for i, pain in enumerate(pains):
        subset = turns[masks[pain.key]].copy()
        if subset.empty:
            continue
        subset["priority"] = (
            subset["rating"].map({"down": 0, "up": 1, "unrated": 2}).fillna(2)
        )
        subset = subset.sort_values(
            ["priority", "repeated_review_concept", "avg_latency_ms"],
            ascending=[True, False, False],
        )

        # Một nửa ưu tiên case mạnh, một nửa random để tránh cherry-pick.
        head_n = min(max(1, n // 2), len(subset))
        head = subset.head(head_n)
        remainder = subset.drop(head.index)
        random_n = min(n - head_n, len(remainder))
        random_part = (
            remainder.sample(random_n, random_state=seed + i)
            if random_n > 0
            else remainder.head(0)
        )
        chosen = pd.concat([head, random_part]).head(n).copy()
        chosen.insert(0, "pain_key", pain.key)
        chosen.insert(1, "pain_title", pain.title)
        frames.append(chosen)

    if not frames:
        return pd.DataFrame()

    evidence = pd.concat(frames, ignore_index=True)
    return evidence[
        [
            "pain_key",
            "pain_title",
            "turn_id",
            "conversation_id",
            "user_id",
            "question",
            "answer",
            "move_used",
            "citations",
            "rating",
            "avg_latency_ms",
        ]
    ]


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def save_figure(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


def plot_move_distribution(turns: pd.DataFrame, figures_dir: Path) -> None:
    counts = turns["move_used"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    counts.plot(kind="barh", ax=ax)
    ax.set_title("Tutor pedagogical move distribution")
    ax.set_xlabel("Number of turns")
    ax.set_ylabel("Move")
    for i, value in enumerate(counts.values):
        ax.text(value, i, f" {value} ({pct(value, len(turns)):.1f}%)", va="center")
    save_figure(figures_dir / "01_move_distribution.png")


def plot_learning_loop_and_grounding(turns: pd.DataFrame, figures_dir: Path) -> None:
    rates = pd.Series(
        {
            "Has citation": turns["has_citation"].mean() * 100,
            "Has check question": turns["has_detected_check_question"].mean() * 100,
            "Has misconception": (turns["misconception_count"] > 0).mean() * 100,
            "Has follow-up": (turns["follow_up_count"] > 0).mean() * 100,
        }
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    rates.plot(kind="bar", ax=ax)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Rate (%)")
    ax.set_title("Grounding and learning-loop signals")
    ax.tick_params(axis="x", rotation=20)
    for i, value in enumerate(rates.values):
        ax.text(i, value + 1, f"{value:.1f}%", ha="center")
    save_figure(figures_dir / "02_learning_loop_and_grounding.png")


def plot_latency_distribution(turns: pd.DataFrame, figures_dir: Path) -> None:
    latency = turns["latency_s"].dropna()
    if latency.empty:
        return
    upper = float(latency.quantile(0.99))
    clipped = latency.clip(upper=upper)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(clipped, bins=35)
    median = float(latency.median())
    p90 = float(latency.quantile(0.90))
    ax.axvline(median, linestyle="--", label=f"Median: {median:.2f}s")
    ax.axvline(p90, linestyle=":", label=f"P90: {p90:.2f}s")
    ax.set_title("Latency distribution (values clipped at p99 for display)")
    ax.set_xlabel("Average latency per turn (seconds)")
    ax.set_ylabel("Turns")
    ax.legend()
    save_figure(figures_dir / "03_latency_distribution.png")


def plot_answer_length_by_move(turns: pd.DataFrame, figures_dir: Path) -> None:
    top_moves = turns["move_used"].value_counts().head(6).index.tolist()
    data = [turns.loc[turns["move_used"].eq(move), "answer_words"].values for move in top_moves]
    if not data:
        return
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.boxplot(data, showfliers=False)
    ax.set_xticks(range(1, len(top_moves) + 1), labels=top_moves)
    ax.set_title("Answer length by pedagogical move")
    ax.set_ylabel("Answer length (words)")
    ax.tick_params(axis="x", rotation=25)
    save_figure(figures_dir / "04_answer_length_by_move.png")


def plot_conversation_turns(conversations: pd.DataFrame, figures_dir: Path) -> None:
    turn_counts = conversations["turn_count"].clip(upper=conversations["turn_count"].quantile(0.99))
    bins = np.arange(0.5, max(2.5, turn_counts.max() + 1.5), 1)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(turn_counts, bins=bins)
    ax.set_title("Turns per conversation (clipped at p99 for display)")
    ax.set_xlabel("Number of turns")
    ax.set_ylabel("Conversations")
    save_figure(figures_dir / "05_conversation_turns.png")


def plot_rating_slices(turns: pd.DataFrame, figures_dir: Path) -> None:
    rows: list[dict[str, Any]] = []
    for name, mask in {
        "Citation": turns["has_citation"],
        "No citation": ~turns["has_citation"],
        "Check": turns["has_detected_check_question"],
        "No check": ~turns["has_detected_check_question"],
        "Review concept": turns["move_used"].eq("review_concept"),
        "Other move": ~turns["move_used"].eq("review_concept"),
    }.items():
        subset = turns[mask & turns["rating"].isin(["up", "down"])]
        rows.append(
            {
                "slice": name,
                "rated_n": len(subset),
                "down_pct": pct(subset["rating"].eq("down").sum(), len(subset)),
            }
        )
    result = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(result["slice"], result["down_pct"])
    ax.set_ylabel("Down rating among rated turns (%)")
    ax.set_title("Exploratory rating slices — interpret cautiously")
    ax.tick_params(axis="x", rotation=25)
    for i, row in result.iterrows():
        ax.text(i, row["down_pct"] + 1, f"{row['down_pct']:.1f}%\nn={row['rated_n']}", ha="center")
    save_figure(figures_dir / "06_rating_slices.png")


def create_figures(turns: pd.DataFrame, conversations: pd.DataFrame, figures_dir: Path) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    plot_move_distribution(turns, figures_dir)
    plot_learning_loop_and_grounding(turns, figures_dir)
    plot_latency_distribution(turns, figures_dir)
    plot_answer_length_by_move(turns, figures_dir)
    plot_conversation_turns(conversations, figures_dir)
    plot_rating_slices(turns, figures_dir)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def markdown_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    if df.empty:
        return "_Không có dữ liệu._"

    columns = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join(["---"] * len(columns)) + "|",
    ]
    for _, row in df.iterrows():
        values = [markdown_escape(row[c]) for c in df.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_report(
    metrics: dict[str, Any],
    turns: pd.DataFrame,
    conversations: pd.DataFrame,
    pains: list[PainCandidate],
    evidence: pd.DataFrame,
) -> str:
    overview = metrics["overview"]
    pedagogy = metrics["pedagogy"]
    loop = metrics["learning_loop"]
    grounding = metrics["grounding"]
    feedback = metrics["feedback"]
    performance = metrics["performance"]

    move_table = value_count_table(turns["move_used"], len(turns), "move")

    pain_rows = []
    for pain in pains:
        pain_rows.append(
            {
                "Pain candidate": pain.title,
                "Turns": f"{pain.affected_turns}/{pain.total_turns} ({pain.affected_turn_pct:.1f}%)",
                "Users": f"{pain.affected_users}/{pain.total_users} ({pain.affected_user_pct:.1f}%)",
                "Conversations": (
                    f"{pain.affected_conversations}/{pain.total_conversations} "
                    f"({pain.affected_conversation_pct:.1f}%)"
                ),
                "Definition": pain.evidence_definition,
            }
        )

    report = f"""# VLearn Chatlog — EDA & Product Insight Report

> Báo cáo được tạo tự động từ dữ liệu local. Các heuristic chỉ dùng để tìm mẫu và
> hình thành giả thuyết; trước khi chốt evidence, nhóm cần review thủ công các ví dụ
> trong `annotation_sample.csv` và giữ tối thiểu 5 trích dẫn nguyên văn cho pain chính.

## 1. Dataset overview

| Metric | Value |
|---|---:|
| Complete student–tutor turns | {overview['turns']:,} |
| Anonymous users | {overview['users']:,} |
| Conversations | {overview['conversations']:,} |
| Multi-turn conversations | {overview['multi_turn_conversations']:,} ({overview['multi_turn_conversation_pct']:.1f}%) |
| Mean turns per user | {overview['turns_per_user_mean']} |
| Mean turns per conversation | {overview['turns_per_conversation_mean']} |
| Time range | {overview['date_min']} → {overview['date_max']} |

## 2. Data quality

| Check | Value |
|---|---:|
| Raw rows | {metrics['data_quality']['raw_rows']:,} |
| Complete turn pairs | {metrics['data_quality']['complete_turn_pairs']:,} |
| Incomplete/duplicate turns excluded | {metrics['data_quality']['incomplete_or_duplicate_turns']:,} |
| Duplicate message IDs | {metrics['data_quality']['duplicate_message_ids']:,} |
| Duplicate `(turn_id, role)` rows | {metrics['data_quality']['duplicated_turn_role_rows']:,} |

## 3. Main descriptive findings

### 3.1 Tutor pedagogical moves

{markdown_table(move_table)}

![Move distribution](figures/01_move_distribution.png)

**Observable finding:** `review_concept` chiếm **{pedagogy['review_concept_pct']:.2f}%**
({pedagogy['review_concept_count']:,}/{overview['turns']:,}) số turn. Có
**{pedagogy['repeated_review_concept_count']:,}** lượt mà `review_concept` xuất hiện
liên tiếp sau một `review_concept` khác trong cùng conversation.

Điều này chưa tự động chứng minh chất lượng kém, nhưng cho thấy policy hiện tại có
độ đa dạng thấp và tạo ra một giả thuyết cần kiểm tra: khi học viên hỏi tiếp, tutor
có thực sự đổi cách dạy hay chỉ tiếp tục giải thích lại?

### 3.2 Learning-loop signals

| Signal | Count | Rate |
|---|---:|---:|
| Detected comprehension check | {loop['check_question_count']:,} | {loop['check_question_pct']:.2f}% |
| `asked_check_question=True` | {loop['check_question_field_true']:,} | {pct(loop['check_question_field_true'], overview['turns']):.2f}% |
| Non-empty misconception | {loop['misconception_nonempty']:,} | {loop['misconception_nonempty_pct']:.2f}% |
| Non-empty follow-up | {loop['follow_up_nonempty']:,} | {loop['follow_up_nonempty_pct']:.2f}% |

![Learning loop and grounding](figures/02_learning_loop_and_grounding.png)

**Observable finding:** hệ thống tạo câu trả lời nhưng thu được rất ít structured
signal về việc học viên hiểu đúng, hiểu sai hoặc nên học gì tiếp. Đây là evidence
mạnh cho **khoảng trống learning loop**, nhưng tác động lên người học vẫn cần được
xác nhận bằng survey/phỏng vấn.

### 3.3 Grounding and trust

| Signal | Count | Rate |
|---|---:|---:|
| Responses with citation | {grounding['with_citation']:,} | {grounding['with_citation_pct']:.2f}% |
| Responses without citation | {grounding['without_citation']:,} | {grounding['without_citation_pct']:.2f}% |

Citation rỗng không đồng nghĩa chắc chắn với hallucination. Một số câu hỏi thao tác
UI hoặc ngoài phạm vi không cần citation. Do đó cần annotation riêng các câu hỏi
kiến thức trước khi tuyên bố tỷ lệ “ungrounded answer”.

### 3.4 Feedback coverage

| Signal | Value |
|---|---:|
| Rated turns | {feedback['rated_count']:,} ({feedback['rated_pct']:.2f}%) |
| Up ratings | {feedback['up_count']:,} |
| Down ratings | {feedback['down_count']:,} |
| Down among rated turns | {feedback['down_among_rated_pct']:.2f}% |

![Rating slices](figures/06_rating_slices.png)

Rating coverage thấp nên không dùng để kết luận causal. Down-rated turns nên được
ưu tiên làm qualitative evidence và golden-set candidates.

### 3.5 Latency, calls and output length

| Metric | Value |
|---|---:|
| Median latency | {performance['latency_ms_median']} ms |
| P90 latency | {performance['latency_ms_p90']} ms |
| P95 latency | {performance['latency_ms_p95']} ms |
| Maximum latency | {performance['latency_ms_max']} ms |
| Mean LLM calls per turn | {performance['llm_call_count_mean']} |
| Median answer length | {performance['answer_words_median']} words |
| P90 answer length | {performance['answer_words_p90']} words |

![Latency distribution](figures/03_latency_distribution.png)

![Answer length by move](figures/04_answer_length_by_move.png)

## 4. Pain candidates — impact table from observed data

{markdown_table(pd.DataFrame(pain_rows))}

### Recommended ordering

1. **Learning loop and strategy adaptation** — chọn làm pain chính nếu manual review
   xác nhận nhiều conversation mà học viên hỏi lại nhưng tutor không đổi cách hỗ trợ.
2. **Grounding/citation** — giữ làm safety and trust constraint, đồng thời kiểm tra
   riêng trên các câu hỏi kiến thức.
3. **Latency** — pain kỹ thuật có thật nhưng chưa có bằng chứng cho thấy là trở ngại
   học tập lớn nhất.

## 5. Product insight chain

### Data observation

- Phần lớn lượt được gắn cùng một pedagogical move.
- Comprehension checks, misconception records và follow-ups xuất hiện rất ít.
- Một phần đáng kể output không có citation.

### Product hypothesis

Tutor hiện tại tối ưu cho việc **tạo ra câu trả lời cho từng lượt**, nhưng chưa tối ưu
cho việc **nhận biết học viên đã hiểu đến đâu và thay đổi chiến lược ở lượt tiếp theo**.

### User pain to validate

> Học viên đang cố hiểu một khái niệm nhận được lời giải thích, nhưng không biết mình
> đã hiểu đúng hay chưa; khi vẫn chưa hiểu, lượt hỗ trợ tiếp theo có thể tiếp tục cùng
> một kiểu giải thích thay vì xử lý đúng điểm mắc.

### Problem statement draft — không chứa solution

> Học viên đang tự học từ tài liệu thường không biết liệu mình đã hiểu đúng một khái
> niệm sau khi được giải thích hay chưa. Những điểm hiểu sai không được nhận diện,
> khiến các lượt hỗ trợ tiếp theo thiếu căn cứ để điều chỉnh theo khó khăn thực tế của
> từng người.

### Prototype slice draft

> Với một học viên đang hỏi về một khái niệm trong tài liệu, hệ thống quyết định nước
> đi sư phạm tiếp theo dựa trên nguồn học và tín hiệu hiểu bài hiện có, để tạo một phản
> hồi giúp phát hiện hoặc xử lý điểm học viên chưa hiểu.

## 6. Evidence examples

"""

    if evidence.empty:
        report += "_Không có evidence sample._\n"
    else:
        for pain_key, group in evidence.groupby("pain_key", sort=False):
            title = group["pain_title"].iloc[0]
            report += f"### {title}\n\n"
            rows = group[["turn_id", "question", "answer", "move_used", "rating"]].copy()
            rows["question"] = rows["question"].map(lambda x: markdown_escape(x, 220))
            rows["answer"] = rows["answer"].map(lambda x: markdown_escape(x, 260))
            report += markdown_table(rows) + "\n\n"

    report += f"""## 7. Manual review protocol

Review `annotation_sample.csv` bằng hai người độc lập. Với mỗi turn, đánh dấu:

1. Câu hỏi thuộc intent nào?
2. Tutor có trả lời đúng intent và đúng kiến thức không?
3. Citation có thực sự support claim không?
4. Tutor có sử dụng context/lịch sử học viên không?
5. Nếu đây là lượt hỏi tiếp, tutor có đổi chiến lược không?
6. Có cần kiểm tra hiểu bài hoặc phát hiện misconception không?
7. Pedagogical move tốt nhất đáng lẽ là gì?

Chỉ dùng một pain làm evidence cuối khi có:

- số đếm và quy tắc đếm kiểm lại được;
- số user/conversation bị ảnh hưởng;
- ít nhất 5 ví dụ nguyên văn;
- manual agreement đủ tốt giữa hai annotator;
- survey xác nhận hậu quả mà data log chưa đo trực tiếp.

## 8. Files generated

- `turn_level_analysis.csv`: một dòng/cặp hỏi-đáp với toàn bộ feature heuristic.
- `conversation_level_analysis.csv`: signal thích ứng ở cấp hội thoại.
- `annotation_sample.csv`: mẫu review thủ công có sẵn cột điền nhãn.
- `evidence_examples.csv`: ví dụ nguyên văn theo từng pain candidate.
- `metrics.json`: số liệu máy đọc được.
- `CP1_DRAFT.md`: Canvas nháp để gặp TA.
"""
    return report


def build_cp1_draft(metrics: dict[str, Any], pains: list[PainCandidate]) -> str:
    overview = metrics["overview"]
    pedagogy = metrics["pedagogy"]
    loop = metrics["learning_loop"]
    grounding = metrics["grounding"]

    pain_table = pd.DataFrame(
        [
            {
                "Ứng viên": p.title,
                "Turn bị ảnh hưởng": f"{p.affected_turn_pct:.1f}%",
                "User bị ảnh hưởng": f"{p.affected_user_pct:.1f}%",
                "Conversation bị ảnh hưởng": f"{p.affected_conversation_pct:.1f}%",
                "Quyết định": (
                    "Chọn/validate sâu"
                    if p.key in {"missing_learning_loop", "no_strategy_change"}
                    else "Constraint hoặc loại khỏi scope"
                ),
            }
            for p in pains
        ]
    )

    return f"""# CP1 Canvas Draft — VLearn

## 1. Hướng

**Hướng A — Tối ưu tutor hiện có trên VLearn.**

## 2. Job executor

Học viên đang tự học một bài trên VLearn và bị mắc ở một khái niệm cụ thể trong tài liệu.

## 3. Job to be Done

Hiểu đúng khái niệm đang học để có thể tiếp tục phần tiếp theo, đồng thời biết mình
đã hiểu đúng hay vẫn còn nhầm ở điểm nào.

## 4. Evidence ban đầu từ data

Dataset có **{overview['turns']:,}** lượt hỏi-đáp, **{overview['users']:,}** user và
**{overview['conversations']:,}** conversation.

- `review_concept` chiếm **{pedagogy['review_concept_pct']:.2f}%** số lượt.
- Chỉ **{loop['check_question_count']:,}** lượt ({loop['check_question_pct']:.2f}%)
  có dấu hiệu hỏi kiểm tra hiểu bài theo field hoặc heuristic.
- Misconception non-empty: **{loop['misconception_nonempty']:,}** lượt.
- Follow-up non-empty: **{loop['follow_up_nonempty']:,}** lượt.
- **{grounding['without_citation_pct']:.2f}%** output không có citation.

> Lưu ý: cần bổ sung 5 ví dụ nguyên văn đã manual-review và khảo sát user để xác nhận hậu quả.

## 5. Painpoint draft

Học viên thường nhận được lời giải thích nhưng không có đủ tín hiệu để biết mình đã
hiểu đúng hay chưa. Khi học viên tiếp tục gặp khó khăn, tutor có thể chưa đổi cách hỗ
trợ theo điểm mắc thực tế, khiến hiểu lầm không được phát hiện và việc học bị kéo dài.

## 6. Problem statement — không chứa AI/solution

Học viên đang tự học từ tài liệu thường không biết liệu mình đã hiểu đúng một khái
niệm sau khi được giải thích hay chưa. Những điểm hiểu sai không được nhận diện,
khiến các lượt hỗ trợ tiếp theo thiếu căn cứ để điều chỉnh theo khó khăn thực tế của
từng người.

## 7. Impact table

{markdown_table(pain_table)}

## 8. Lát cắt prototype

Với một học viên đang hỏi về một khái niệm trong tài liệu, hệ thống quyết định nước
đi sư phạm tiếp theo dựa trên nguồn học và tín hiệu hiểu bài hiện có, để tạo một phản
hồi giúp phát hiện hoặc xử lý điểm học viên chưa hiểu.

## 9. Automation dự kiến

**Conditional automation.** Hệ thống tự thực hiện khi có đủ nguồn và context; khi
thiếu căn cứ hoặc input mơ hồ, hệ thống hỏi làm rõ hoặc nói rõ giới hạn.

## 10. User sẵn sàng thử

- [Tên 1]
- [Tên 2]
- [Tên 3]

## 11. Phân công

- Quốc Khánh: data mining, problem framing, policy/agent logic.
- [Thành viên 2]: manual annotation và user research.
- [Thành viên 3]: frontend prototype.
- [Thành viên 4]: evaluation, validation và documentation.
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = args.output_dir / "figures"

    print(f"[1/7] Loading: {args.input}")
    raw = load_data(args.input)

    print("[2/7] Validating data")
    quality = validate_data(raw)

    print("[3/7] Building turn-level and conversation-level tables")
    turns = build_turn_table(raw)
    conversations = build_conversation_table(turns)

    print("[4/7] Computing metrics and pain candidates")
    pains = build_pain_candidates(turns)
    metrics = build_metrics(raw, quality, turns, conversations, pains)

    print("[5/7] Sampling evidence and annotation cases")
    evidence = sample_evidence(
        turns,
        pains,
        n=args.examples_per_pain,
        seed=args.seed,
    )
    annotation = stratified_annotation_sample(
        turns,
        sample_size=args.sample_size,
        seed=args.seed,
    )

    print("[6/7] Creating figures")
    create_figures(turns, conversations, figures_dir)

    print("[7/7] Writing outputs")
    turns.to_csv(args.output_dir / "turn_level_analysis.csv", index=False)
    conversations.to_csv(args.output_dir / "conversation_level_analysis.csv", index=False)
    evidence.to_csv(args.output_dir / "evidence_examples.csv", index=False)
    annotation.to_csv(args.output_dir / "annotation_sample.csv", index=False)
    json_dump(args.output_dir / "metrics.json", metrics)

    report = build_report(metrics, turns, conversations, pains, evidence)
    (args.output_dir / "EDA_REPORT.md").write_text(report, encoding="utf-8")

    cp1 = build_cp1_draft(metrics, pains)
    (args.output_dir / "CP1_DRAFT.md").write_text(cp1, encoding="utf-8")

    print("\nDone.")
    print(f"EDA report : {args.output_dir / 'EDA_REPORT.md'}")
    print(f"CP1 draft  : {args.output_dir / 'CP1_DRAFT.md'}")
    print(f"Annotation : {args.output_dir / 'annotation_sample.csv'}")
    print(f"Figures    : {figures_dir}")
    print("\nHãy manual-review annotation_sample.csv trước khi chốt insight cuối.")


if __name__ == "__main__":
    main()
