"""
VLearn Adaptive Tutor Python FastAPI Backend Server
Integrated with Google Gemini 3.1 Flash Lite / Gemini 3 Flash
Reads actual PDF slides from data/vlearn-pack/slides/ (d1-slide-hackathon.pdf & d2-slide-hackathon.pdf)
"""
import os
import sys
import json
from functools import lru_cache
import fitz
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

# Import Slide Loader and Tool Modules
from backend.slide_loader import ALL_PDF_SLIDES
from backend.gemini_client import call_gemini_json
from backend.tools.grounded_answer.tool import run_grounded_answer_tool, GroundedAnswerInput
from backend.tools.orchestrator.tool import run_orchestrator_tool, OrchestratorInput
from backend.tools.clarification.tool import run_clarification_tool, ClarificationInput
from backend.tools.understanding_check.tool import run_understanding_check_tool, UnderstandingCheckInput
from backend.tools.misconception_detection.tool import run_misconception_detection_tool, MisconceptionInput
from backend.tools.followup_suggestions.tool import run_followup_suggestions_tool, FollowupInput

app = FastAPI(
    title="VLearn Adaptive Tutor Multi-Agent Backend",
    description="Python FastAPI backend powering VLearn Adaptive Learning Loop Orchestrator",
    version="1.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Models
class AskRequest(BaseModel):
    question: str
    selected_text: Optional[str] = ""
    page_number: Optional[int] = 1
    chat_history: Optional[List[dict]] = []
    api_key: Optional[str] = None

class QuizSubmitRequest(BaseModel):
    quiz_id: str
    quiz_type: Optional[str] = "multiple_choice"
    selected_option: Optional[int] = None
    correct_option: Optional[int] = None
    user_text_answer: Optional[str] = ""
    expected_keywords: Optional[List[str]] = []
    question_text: str
    page_number: Optional[int] = 1
    api_key: Optional[str] = None

# 1. Slide List API (Serves actual PDF slide pages extracted from d1 & d2)
@app.get("/api/slides")
def get_slides(deck: Optional[str] = None):
    slides = ALL_PDF_SLIDES
    if deck:
        slides = [s for s in ALL_PDF_SLIDES if s.get("deck_id") == deck]

    return {
        "total_pages": len(slides),
        "slides": slides,
        "pdf_decks": [
            {"id": "d1", "name": "d1-slide-hackathon.pdf (Day 1: AI & LLM Foundation)"},
            {"id": "d2", "name": "d2-slide-hackathon.pdf (Day 2: Xác định bài toán cho AI)"}
        ]
    }


@lru_cache(maxsize=128)
def _render_slide_png(page_number: int) -> bytes:
    slide = next((item for item in ALL_PDF_SLIDES if item.get("page") == page_number), None)
    if not slide:
        raise ValueError("Slide page not found")

    filename = str(slide.get("code", "")).split("#", 1)[0]
    pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/vlearn-pack/slides", filename))
    slides_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/vlearn-pack/slides"))
    if os.path.commonpath([pdf_path, slides_root]) != slides_root or not os.path.isfile(pdf_path):
        raise ValueError("Slide source not found")

    with fitz.open(pdf_path) as document:
        page_index = int(slide.get("page_in_deck", 1)) - 1
        if page_index < 0 or page_index >= document.page_count:
            raise ValueError("PDF page not found")
        page = document.load_page(page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        return pixmap.tobytes("png")


@app.get("/api/slides/{page_number}/render")
def render_slide(page_number: int):
    """Render the original PDF page faithfully, including diagrams and artwork."""
    try:
        image_bytes = _render_slide_png(page_number)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"}
    )

# 2. Main Multi-Agent Pipeline Endpoint
@app.post("/api/tutor/ask")
def tutor_ask(req: AskRequest):
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    api_key = req.api_key or os.environ.get("GEMINI_API_KEY")

    initial_answer = f"Trả lời cho câu hỏi '{req.question}' trên slide {req.page_number}"
    decision = run_orchestrator_tool(OrchestratorInput(
        question=req.question,
        tutor_answer=initial_answer,
        chat_history=req.chat_history,
        api_key=api_key
    ))

    is_deep_dive = (decision.branch == "followup")

    grounded = run_grounded_answer_tool(GroundedAnswerInput(
        question=req.question,
        selected_text=req.selected_text,
        page_number=req.page_number,
        is_deep_dive=is_deep_dive,
        api_key=api_key
    ))

    default_followup = run_followup_suggestions_tool(FollowupInput(
        tutor_answer=grounded.answer,
        page_number=req.page_number,
        api_key=api_key
    )).suggestions

    tool_result = None

    if decision.branch == "clarify":
        tool_result = run_clarification_tool(ClarificationInput(
            question=req.question,
            page_number=req.page_number,
            api_key=api_key
        )).model_dump()
    elif decision.branch == "understanding_check" or decision.branch == "followup":
        tool_result = run_understanding_check_tool(UnderstandingCheckInput(
            question=req.question,
            tutor_answer=grounded.answer,
            page_number=req.page_number,
            api_key=api_key
        )).model_dump()

    return {
        "status": "success",
        "answer": grounded.answer,
        "citations": grounded.citations,
        "orchestrator": decision.model_dump(),
        "tool_data": tool_result,
        "default_suggestions": default_followup,
        "page": req.page_number,
        "model_engine": "Gemini 3.1 Flash Lite / Gemini 3 Flash"
    }


@app.post("/api/tutor/ask/stream")
def tutor_ask_stream(req: AskRequest):
    """Stream observable tool execution events, then the completed tutor result."""
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    def event_stream():
        api_key = req.api_key or os.environ.get("GEMINI_API_KEY")

        def emit(event_type: str, **payload):
            return f"data: {json.dumps({'type': event_type, **payload}, ensure_ascii=False)}\n\n"

        try:
            yield emit("trace", tool="orchestrator", title="Learning Loop Orchestrator", status="running", detail="Đang phân tích câu hỏi và chọn nhánh học tập")
            initial_answer = f"Trả lời cho câu hỏi '{req.question}' trên slide {req.page_number}"
            decision = run_orchestrator_tool(OrchestratorInput(
                question=req.question,
                tutor_answer=initial_answer,
                chat_history=req.chat_history,
                api_key=api_key
            ))
            yield emit("trace", tool="orchestrator", title="Learning Loop Orchestrator", status="completed", detail=f"Đã chọn: {decision.title}")

            yield emit("trace", tool="grounded_answer", title="Grounded Answer Tool", status="running", detail="Đang đọc slide liên quan và tạo câu trả lời có căn cứ")
            grounded = run_grounded_answer_tool(GroundedAnswerInput(
                question=req.question,
                selected_text=req.selected_text,
                page_number=req.page_number,
                is_deep_dive=(decision.branch == "followup"),
                api_key=api_key
            ))
            cited_pages = ", ".join(str(page) for page in grounded.citations) or "không có"
            yield emit("trace", tool="grounded_answer", title="Grounded Answer Tool", status="completed", detail=f"Hoàn tất · nguồn trang {cited_pages}")

            yield emit("trace", tool="followup_suggestions", title="Follow-up Suggestions Tool", status="running", detail="Đang chuẩn bị câu hỏi gợi mở phù hợp")
            default_followup = run_followup_suggestions_tool(FollowupInput(
                tutor_answer=grounded.answer,
                page_number=req.page_number,
                api_key=api_key
            )).suggestions
            yield emit("trace", tool="followup_suggestions", title="Follow-up Suggestions Tool", status="completed", detail=f"Đã tạo {len(default_followup)} gợi ý")

            tool_result = None
            if decision.branch == "clarify":
                yield emit("trace", tool="clarification", title="Clarification Tool", status="running", detail="Đang tạo câu hỏi làm rõ")
                tool_result = run_clarification_tool(ClarificationInput(
                    question=req.question, page_number=req.page_number, api_key=api_key
                )).model_dump()
                yield emit("trace", tool="clarification", title="Clarification Tool", status="completed", detail="Đã chuẩn bị lựa chọn làm rõ")
            elif decision.branch in ("understanding_check", "followup"):
                yield emit("trace", tool="understanding_check", title="Understanding Check Tool", status="running", detail="Đang tạo câu hỏi kiểm tra hiểu")
                tool_result = run_understanding_check_tool(UnderstandingCheckInput(
                    question=req.question,
                    tutor_answer=grounded.answer,
                    page_number=req.page_number,
                    api_key=api_key
                )).model_dump()
                yield emit("trace", tool="understanding_check", title="Understanding Check Tool", status="completed", detail="Đã tạo bài kiểm tra phù hợp")

            result = {
                "status": "success",
                "answer": grounded.answer,
                "citations": grounded.citations,
                "orchestrator": decision.model_dump(),
                "tool_data": tool_result,
                "default_suggestions": default_followup,
                "page": req.page_number,
                "model_engine": "Gemini 3.1 Flash Lite / Gemini 3 Flash"
            }
            yield emit("result", data=result)
        except Exception as error:
            yield emit("error", message="Không thể hoàn tất luồng xử lý.", detail=str(error))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

# 3. Quiz Submit & Misconception Engine Endpoint
@app.post("/api/quiz/submit")
def submit_quiz(req: QuizSubmitRequest):
    api_key = req.api_key or os.environ.get("GEMINI_API_KEY")
    is_correct = False

    if req.quiz_type == "short_answer":
        user_ans = (req.user_text_answer or "").strip().lower()
        if not user_ans:
            is_correct = False
        else:
            eval_prompt = (
                f"Câu hỏi kiểm tra: \"{req.question_text}\"\n"
                f"Câu trả lời của học viên: \"{req.user_text_answer}\"\n\n"
                "Hãy đánh giá xem câu trả lời của học viên có thể hiện hiểu đúng bản chất hay không.\n"
                "Trả về JSON dạng: {\"is_correct\": true/false, \"feedback\": \"...\"}"
            )
            eval_result = call_gemini_json(eval_prompt, api_key=api_key)

            if eval_result and "is_correct" in eval_result:
                is_correct = bool(eval_result.get("is_correct", False))
            else:
                keywords = req.expected_keywords or ["schema", "hợp đồng", "cấu trúc", "json", "chính xác", "context"]
                is_correct = any(kw.lower() in user_ans for kw in keywords) or len(user_ans) > 15
    else:
        is_correct = (req.selected_option is not None and req.correct_option is not None and req.selected_option == req.correct_option)

    if is_correct:
        end_turn_suggestions = run_followup_suggestions_tool(FollowupInput(
            tutor_answer="Học viên đã trả lời đúng. Hãy gợi ý 3 câu hỏi đào sâu để học viên tự chọn sau khi kết thúc lượt.",
            page_number=req.page_number,
            api_key=api_key
        )).suggestions
        return {
            "is_correct": True,
            "feedback": "🎉 Xuất sắc! Bạn đã trả lời chính xác và nắm rất vững bản chất bài học. (Kết thúc lượt)",
            "next_step": "end_turn",
            "default_suggestions": end_turn_suggestions,
            "model_engine": "Gemini 3.1 Flash Lite / Gemini 3 Flash"
        }
    else:
        default_followup = run_followup_suggestions_tool(FollowupInput(
            tutor_answer="Quiz submit result",
            page_number=req.page_number,
            api_key=api_key
        )).suggestions
        misconception = run_misconception_detection_tool(MisconceptionInput(
            question_text=req.question_text,
            selected_option=req.selected_option or 0,
            correct_option=req.correct_option or 1,
            page_number=req.page_number,
            api_key=api_key
        ))
        return {
            "is_correct": False,
            "feedback": "⚠️ Chưa chính xác. AI Tutor đã phân tích nguyên nhân nhầm lẫn bên dưới:",
            "next_step": "misconception_explanation",
            "misconception": misconception.model_dump(),
            "default_suggestions": default_followup,
            "model_engine": "Gemini 3.1 Flash Lite / Gemini 3 Flash"
        }

# 4. Serve Static Frontend Files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
