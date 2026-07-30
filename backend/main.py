"""
VLearn Adaptive Tutor FastAPI backend.

This module keeps the existing REST surface used by the frontend while routing
chatbot reasoning through ai_core's LangGraph learning loop.
"""

from __future__ import annotations

import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.slide_loader import ALL_PDF_SLIDES

ROOT_DIR = Path(__file__).resolve().parents[1]
AI_CORE_DIR = ROOT_DIR / "ai_core"
if str(AI_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_CORE_DIR))

try:
    from vlearn_ai import VLearnAICore
    from vlearn_ai.config import reset_settings
    from vlearn_ai.schemas import AICoreBaseError, InvalidResumeStateError
except Exception as import_error:  # pragma: no cover - surfaced by health/API responses
    VLearnAICore = None  # type: ignore[assignment]
    reset_settings = None  # type: ignore[assignment]
    AICoreBaseError = Exception  # type: ignore[assignment]
    InvalidResumeStateError = Exception  # type: ignore[assignment]
    AI_CORE_IMPORT_ERROR = import_error
else:
    AI_CORE_IMPORT_ERROR = None


def _load_env_file(path: Path) -> None:
    """Load key=value env files without logging secrets."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


_load_env_file(ROOT_DIR / ".env")
_load_env_file(AI_CORE_DIR / ".env")

app = FastAPI(
    title="VLearn Adaptive Tutor Backend",
    description="FastAPI backend powered by VLearn AI Core LangGraph learning loop.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    selected_text: Optional[str] = ""
    page_number: Optional[int] = 1
    chat_history: Optional[list[dict[str, Any]]] = Field(default_factory=list)
    thread_id: Optional[str] = None
    api_key: Optional[str] = None
    openai_api_key: Optional[str] = None


class QuizSubmitRequest(BaseModel):
    quiz_id: str
    thread_id: Optional[str] = None
    quiz_type: Optional[str] = "multiple_choice"
    selected_option: Optional[int] = None
    correct_option: Optional[int] = None
    user_text_answer: Optional[str] = ""
    expected_keywords: Optional[list[str]] = Field(default_factory=list)
    question_text: str
    page_number: Optional[int] = 1
    api_key: Optional[str] = None
    openai_api_key: Optional[str] = None


class ClarificationSubmitRequest(BaseModel):
    thread_id: str
    answer: str
    api_key: Optional[str] = None
    openai_api_key: Optional[str] = None


AI_CORE: VLearnAICore | None = None
ACTIVE_THREADS: dict[str, dict[str, Any]] = {}
QUIZ_SESSIONS: dict[str, dict[str, Any]] = {}


def _get_ai_core() -> VLearnAICore:
    global AI_CORE
    if AI_CORE_IMPORT_ERROR is not None or VLearnAICore is None:
        raise HTTPException(
            status_code=500,
            detail=f"ai_core import failed: {AI_CORE_IMPORT_ERROR}",
        )
    if AI_CORE is None:
        AI_CORE = VLearnAICore()
    return AI_CORE


def _apply_request_api_key(api_key: str | None) -> None:
    """Support BYOK without printing/storing the key in responses."""
    key = (api_key or "").strip()
    if key and not key.startswith("AIza"):
        os.environ["OPENAI_API_KEY"] = key
        if reset_settings is not None:
            reset_settings()


def _resolve_slide(page_number: int | None) -> dict[str, Any] | None:
    if not ALL_PDF_SLIDES:
        return None

    page = max(1, int(page_number or 1))
    for slide in ALL_PDF_SLIDES:
        if int(slide.get("page", -1)) == page:
            return slide
    return ALL_PDF_SLIDES[0]


def _build_selected_context(req: AskRequest) -> str:
    slide = _resolve_slide(req.page_number)
    pieces: list[str] = []

    if slide:
        pieces.append(
            f"Nguồn: [trang {slide.get('page')}] {slide.get('deck_name', '')} "
            f"(slide {slide.get('page_in_deck', slide.get('page'))})"
        )
        pieces.append(f"Tiêu đề: {slide.get('title', '')}")
        if slide.get("subtitle"):
            pieces.append(f"Phụ đề: {slide.get('subtitle')}")
        if slide.get("raw_text"):
            pieces.append(str(slide.get("raw_text")))

    selected = (req.selected_text or "").strip()
    if selected:
        pieces.append(f"Đoạn học viên chọn: {selected}")

    return "\n\n".join(p for p in pieces if p).strip() or selected


def _extract_pages(citations: list[dict[str, Any]], fallback_page: int | None) -> list[int]:
    pages: list[int] = []
    for citation in citations:
        haystack = " ".join(
            str(citation.get(key, ""))
            for key in ("citation_id", "source_location", "snippet")
        )
        match = re.search(r"(?:trang|page|p)\D*(\d{1,3})", haystack, re.IGNORECASE)
        if match:
            pages.append(int(match.group(1)))

    if not pages and fallback_page:
        pages.append(int(fallback_page))

    return sorted(set(page for page in pages if 1 <= page <= 999))


def _build_sources(
    citations: list[dict[str, Any]],
    pages: list[int],
    fallback_page: int | None,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    pages_to_emit = pages or ([int(fallback_page)] if fallback_page else [])

    for page in pages_to_emit:
        slide = _resolve_slide(page)
        citation_for_page = next(
            (
                c
                for c in citations
                if str(page) in str(c.get("source_location", ""))
                or str(page) in str(c.get("citation_id", ""))
            ),
            None,
        )
        snippet = (
            citation_for_page.get("snippet")
            if citation_for_page
            else (slide or {}).get("raw_text", "")
        )
        sources.append(
            {
                "page": page,
                "title": (slide or {}).get("title") or f"Slide {page}",
                "snippet": str(snippet or "")[:260],
                "source_location": (citation_for_page or {}).get(
                    "source_location", f"trang {page}"
                ),
            }
        )

    return sources


def _append_page_marker(answer: str, pages: list[int]) -> str:
    if not answer or not pages:
        return answer
    if re.search(r"\[trang\s+\d+\]", answer, flags=re.IGNORECASE):
        return answer
    markers = " ".join(f"[trang {page}]" for page in pages[:3])
    return f"{answer}\n\n{markers}"


def _branch_from_result(result: dict[str, Any]) -> str:
    status = result.get("status")
    route_name = (result.get("route") or {}).get("name")
    ui_type = (result.get("ui_payload") or {}).get("type")

    if status == "awaiting_clarification":
        return "clarify"
    if status == "awaiting_check" or ui_type in {
        "multiple_choice",
        "short_answer",
        "micro_check",
    }:
        return "understanding_check"
    if result.get("followups"):
        return "followup"
    return route_name or "simple"


def _orchestrator_payload(result: dict[str, Any]) -> dict[str, Any]:
    route = result.get("route") or {}
    branch = _branch_from_result(result)
    titles = {
        "simple": "Câu hỏi đơn giản",
        "clarify": "Thiếu thông tin → Hỏi làm rõ",
        "understanding_check": "Cần kiểm tra hiểu",
        "followup": "Có thể đào sâu → Follow-up Suggestions",
        "deep": "Có thể đào sâu",
        "check": "Cần kiểm tra hiểu",
    }
    return {
        "branch": branch,
        "title": titles.get(branch, branch),
        "description": route.get("reason") or result.get("blocked_reason") or "",
        "next_node": result.get("status"),
        "confidence": route.get("confidence"),
        "route": route.get("name"),
    }


def _format_followups(result: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in result.get("followups") or []:
        if isinstance(item, dict):
            question = item.get("question") or item.get("label")
            if question:
                out.append(str(question))
    return out


def _format_tool_data(
    result: dict[str, Any],
    *,
    thread_id: str,
    page_number: int | None,
) -> dict[str, Any] | None:
    payload = result.get("ui_payload") or {}
    status = result.get("status")
    payload_type = payload.get("type")

    if status == "awaiting_clarification" or payload_type == "clarification_request":
        return {
            "type": "clarification_request",
            "thread_id": thread_id,
            "question": payload.get("question") or result.get("assistant_message"),
            "options": payload.get("options") or [],
        }

    if status != "awaiting_check" and payload_type not in {
        "multiple_choice",
        "short_answer",
        "micro_check",
    }:
        return None

    options = payload.get("options") or []
    correct_option_id = payload.get("correct_option_id")
    correct_index = None
    option_texts: list[str] = []
    for idx, opt in enumerate(options):
        if isinstance(opt, dict):
            option_texts.append(str(opt.get("text", "")))
            if opt.get("option_id") == correct_option_id:
                correct_index = idx
        else:
            option_texts.append(str(opt))

    quiz_id = f"quiz_{thread_id}"
    QUIZ_SESSIONS[quiz_id] = {
        "thread_id": thread_id,
        "payload": payload,
        "page_number": page_number,
    }

    return {
        "quiz_id": quiz_id,
        "thread_id": thread_id,
        "quiz_type": payload_type or "multiple_choice",
        "concept": payload.get("target_concept") or "core_concept",
        "question": payload.get("question"),
        "options": option_texts,
        "correct_index": correct_index,
        "expected_keywords": payload.get("expected_keywords") or [],
        "explanation": payload.get("explanation") or "",
    }


def _format_tutor_response(
    result: dict[str, Any],
    *,
    thread_id: str,
    page_number: int | None,
) -> dict[str, Any]:
    raw_citations = result.get("citations") or []
    pages = _extract_pages(raw_citations, page_number)
    answer = _append_page_marker(result.get("assistant_message") or "", pages)

    return {
        "status": "success" if result.get("status") != "failed" else "failed",
        "thread_id": thread_id,
        "answer": answer,
        "citations": pages,
        "citation_objects": raw_citations,
        "sources": _build_sources(raw_citations, pages, page_number),
        "orchestrator": _orchestrator_payload(result),
        "tool_data": _format_tool_data(
            result,
            thread_id=thread_id,
            page_number=page_number,
        ),
        "default_suggestions": _format_followups(result),
        "page": page_number,
        "ai_core_status": result.get("status"),
        "tool_trace": result.get("tool_trace") or [],
        "model_engine": os.environ.get("OPENAI_MODEL", "gpt-5-nano"),
    }


def _get_check_state(thread_id: str) -> dict[str, Any]:
    core = _get_ai_core()
    snapshot = core.app.get_state({"configurable": {"thread_id": thread_id}})
    return dict(snapshot.values or {}) if snapshot else {}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ai_core_loaded": AI_CORE_IMPORT_ERROR is None,
        "openai_key_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "slide_count": len(ALL_PDF_SLIDES),
    }


@app.get("/api/slides")
def get_slides(deck: Optional[str] = None):
    slides = ALL_PDF_SLIDES
    if deck:
        slides = [s for s in ALL_PDF_SLIDES if s.get("deck_id") == deck]

    return {
        "total_pages": len(slides),
        "slides": slides,
        "pdf_decks": [
            {
                "id": "d1",
                "name": "d1-slide-hackathon.pdf (Day 1: AI & LLM Foundation)",
            },
            {
                "id": "d2",
                "name": "d2-slide-hackathon.pdf (Day 2: Xác định bài toán cho AI)",
            },
        ],
    }


@app.post("/api/tutor/ask/stream")
async def tutor_ask_stream(req: AskRequest):
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    _apply_request_api_key(req.openai_api_key or req.api_key)
    core = _get_ai_core()
    thread_id = req.thread_id or f"thread_{uuid.uuid4().hex}"

    async def event_stream():
        def emit(event_type: str, **payload):
            return f"data: {json.dumps({'type': event_type, **payload}, ensure_ascii=False)}\n\n"

        try:
            yield emit("trace", tool="orchestrator", title="Learning Loop Orchestrator", status="running", detail="Đang phân tích câu hỏi và chọn nhánh học tập")
            
            active = ACTIVE_THREADS.get(thread_id, {})
            if active.get("status") == "awaiting_clarification":
                result = await core.resume_turn(
                    thread_id=thread_id,
                    student_input=req.question,
                )
            else:
                result = await core.start_turn(
                    thread_id=thread_id,
                    question=req.question,
                    selected_context=_build_selected_context(req),
                    conversation_history=req.chat_history or [],
                )

            ACTIVE_THREADS[thread_id] = {
                "status": result.get("status"),
                "updated_at": time.time(),
                "page_number": req.page_number,
            }

            formatted = _format_tutor_response(
                result,
                thread_id=thread_id,
                page_number=req.page_number,
            )

            # Phân tách công đoạn trace giả để UI mượt mà
            yield emit("trace", tool="orchestrator", title="Learning Loop Orchestrator", status="completed", detail=f"Đã chọn nhánh phù hợp")
            yield emit("trace", tool="grounded_answer", title="Grounded Answer Tool", status="running", detail="Đang đọc slide liên quan và tạo câu trả lời")
            yield emit("trace", tool="grounded_answer", title="Grounded Answer Tool", status="completed", detail=f"Hoàn tất xử lý trả lời")
            
            yield emit("result", data=formatted)

        except AICoreBaseError as exc:
            yield emit("error", message="Lỗi logic", detail=str(exc))
        except Exception as error:
            yield emit("error", message="Không thể hoàn tất luồng xử lý.", detail=str(error))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.post("/api/tutor/ask")
async def tutor_ask(req: AskRequest):
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    _apply_request_api_key(req.openai_api_key or req.api_key)
    core = _get_ai_core()
    thread_id = req.thread_id or f"thread_{uuid.uuid4().hex}"

    try:
        active = ACTIVE_THREADS.get(thread_id, {})
        if active.get("status") == "awaiting_clarification":
            result = await core.resume_turn(
                thread_id=thread_id,
                student_input=req.question,
            )
        else:
            result = await core.start_turn(
                thread_id=thread_id,
                question=req.question,
                selected_context=_build_selected_context(req),
                conversation_history=req.chat_history or [],
            )
    except InvalidResumeStateError:
        result = await core.start_turn(
            thread_id=thread_id,
            question=req.question,
            selected_context=_build_selected_context(req),
            conversation_history=req.chat_history or [],
        )
    except AICoreBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI core failed: {exc}") from exc

    ACTIVE_THREADS[thread_id] = {
        "status": result.get("status"),
        "updated_at": time.time(),
        "page_number": req.page_number,
    }
    return _format_tutor_response(
        result,
        thread_id=thread_id,
        page_number=req.page_number,
    )


@app.post("/api/clarification/submit")
async def submit_clarification(req: ClarificationSubmitRequest):
    if not req.answer or not req.answer.strip():
        raise HTTPException(status_code=400, detail="Clarification answer is required")

    _apply_request_api_key(req.openai_api_key or req.api_key)
    core = _get_ai_core()

    try:
        result = await core.resume_turn(
            thread_id=req.thread_id,
            student_input=req.answer,
        )
    except AICoreBaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI core failed: {exc}") from exc

    page_number = ACTIVE_THREADS.get(req.thread_id, {}).get("page_number", 1)
    ACTIVE_THREADS[req.thread_id] = {
        "status": result.get("status"),
        "updated_at": time.time(),
        "page_number": page_number,
    }
    return _format_tutor_response(
        result,
        thread_id=req.thread_id,
        page_number=page_number,
    )


@app.post("/api/quiz/submit")
async def submit_quiz(req: QuizSubmitRequest):
    _apply_request_api_key(req.openai_api_key or req.api_key)

    session = QUIZ_SESSIONS.get(req.quiz_id)
    if not session:
        if req.thread_id:
            thread_id = req.thread_id
            options = []
        else:
            raise HTTPException(
                status_code=404,
                detail="Quiz session not found. Start a tutor turn before submitting quiz.",
            )
    else:
        thread_id = session["thread_id"]
        payload = session.get("payload") or {}
        options = payload.get("options") or []
    selected_answer = (req.user_text_answer or "").strip()

    if req.quiz_type != "short_answer" and req.selected_option is not None:
        idx = int(req.selected_option)
        if 0 <= idx < len(options) and isinstance(options[idx], dict):
            selected_answer = str(options[idx].get("option_id") or options[idx].get("text"))
        else:
            selected_answer = str(req.selected_option)

    if not selected_answer:
        raise HTTPException(status_code=400, detail="Quiz answer is required")

    core = _get_ai_core()
    try:
        result = await core.resume_turn(
            thread_id=thread_id,
            student_input=selected_answer,
        )
    except AICoreBaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI core failed: {exc}") from exc

    state = _get_check_state(thread_id)
    check_result = state.get("check_result") or {}
    is_correct = bool(check_result.get("is_correct"))
    page_number = session.get("page_number") or req.page_number
    formatted = _format_tutor_response(
        result,
        thread_id=thread_id,
        page_number=page_number,
    )

    return {
        "is_correct": is_correct,
        "feedback": (
            "Đúng rồi. Bạn đã nắm đúng ý chính."
            if is_correct
            else check_result.get("error_explanation")
            or "Chưa chính xác. Tutor đã tạo phần sửa hiểu nhầm bên dưới."
        ),
        "next_step": "followup" if is_correct else "misconception_explanation",
        "misconception": check_result if not is_correct else None,
        "tutor_response": formatted,
        "default_suggestions": formatted.get("default_suggestions", []),
        "model_engine": formatted.get("model_engine"),
    }


frontend_dir = ROOT_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
