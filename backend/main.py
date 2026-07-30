"""
VLearn Adaptive Tutor Python FastAPI Backend Server
Integrated with Google Gemini 3.1 Flash Lite / Gemini 3 Flash
Implements Updated Workflow:
1. Default 3 follow-up suggestion chips attached in all cases before ending turn.
2. Branch 'followup' triggers Mở rộng tri thức (Deep-dive Expansion) in LLM answer -> then points to Understanding Check (Quiz).
3. Correct quiz answer -> Ends turn immediately (with 3 default follow-up chips).
"""
import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

# Import Tool Modules
from backend.gemini_client import call_gemini_json
from backend.tools.grounded_answer.tool import run_grounded_answer_tool, GroundedAnswerInput, SLIDE_KNOWLEDGE
from backend.tools.orchestrator.tool import run_orchestrator_tool, OrchestratorInput
from backend.tools.clarification.tool import run_clarification_tool, ClarificationInput
from backend.tools.understanding_check.tool import run_understanding_check_tool, UnderstandingCheckInput
from backend.tools.misconception_detection.tool import run_misconception_detection_tool, MisconceptionInput
from backend.tools.followup_suggestions.tool import run_followup_suggestions_tool, FollowupInput

app = FastAPI(
    title="VLearn Adaptive Tutor Multi-Agent Backend",
    description="Python FastAPI backend powering VLearn Adaptive Learning Loop Orchestrator",
    version="1.3.0"
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

# 1. Slide List API
@app.get("/api/slides")
def get_slides():
    return {
        "total_pages": len(SLIDE_KNOWLEDGE),
        "slides": SLIDE_KNOWLEDGE
    }

# 2. Main Multi-Agent Pipeline Endpoint
@app.post("/api/tutor/ask")
def tutor_ask(req: AskRequest):
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    api_key = req.api_key or os.environ.get("GEMINI_API_KEY")

    # Step 1: Decision by Master Agent "Bước tiếp theo?"
    # First get initial answer for decision context
    initial_answer = f"Trả lời cho câu hỏi '{req.question}' trên slide {req.page_number}"
    decision = run_orchestrator_tool(OrchestratorInput(
        question=req.question,
        tutor_answer=initial_answer,
        chat_history=req.chat_history,
        api_key=api_key
    ))

    # Check if branch is 'followup' -> requires deep-dive knowledge expansion in LLM answer
    is_deep_dive = (decision.branch == "followup")

    # Step 2: Grounded Answer Tool (includes Deep-dive Expansion if branch == 'followup')
    grounded = run_grounded_answer_tool(GroundedAnswerInput(
        question=req.question,
        selected_text=req.selected_text,
        page_number=req.page_number,
        is_deep_dive=is_deep_dive,
        api_key=api_key
    ))

    # Step 3: Default 3 Follow-up Suggestions attached in ALL cases
    default_followup = run_followup_suggestions_tool(FollowupInput(
        tutor_answer=grounded.answer,
        page_number=req.page_number,
        api_key=api_key
    )).suggestions

    # Step 4: Run Decision Branch Tool
    tool_result = None

    if decision.branch == "clarify":
        tool_result = run_clarification_tool(ClarificationInput(
            question=req.question,
            page_number=req.page_number,
            api_key=api_key
        )).model_dump()
    elif decision.branch == "understanding_check" or decision.branch == "followup":
        # Note: If branch is 'followup', after Mở rộng tri thức -> points to Understanding Check (Quiz)!
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

    # 3 Default Follow-up Suggestions attached in ALL cases
    default_followup = run_followup_suggestions_tool(FollowupInput(
        tutor_answer="Quiz submit result",
        page_number=req.page_number,
        api_key=api_key
    )).suggestions

    if is_correct:
        # Correct answer -> End turn immediately (with 3 default follow-up chips)
        return {
            "is_correct": True,
            "feedback": "🎉 Xuất sắc! Bạn đã trả lời chính xác và nắm rất vững bản chất bài học. (Kết thúc lượt)",
            "next_step": "end_turn",
            "default_suggestions": default_followup,
            "model_engine": "Gemini 3.1 Flash Lite / Gemini 3 Flash"
        }
    else:
        # Wrong answer -> Misconception Detection Tool
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
