"""
Tool: Understanding Check (Quiz Generator - Supports Multiple Choice & Short Answer Text Input)
"""
import time
from pydantic import BaseModel
from typing import List, Optional
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from backend.gemini_client import call_gemini_json

class UnderstandingCheckInput(BaseModel):
    question: str
    tutor_answer: str
    page_number: int = 1
    api_key: Optional[str] = None

class UnderstandingCheckOutput(BaseModel):
    quiz_id: str
    quiz_type: str  # "multiple_choice" | "short_answer"
    concept: str
    question: str
    options: Optional[List[str]] = []
    correct_index: Optional[int] = 0
    expected_keywords: Optional[List[str]] = []
    explanation: str

def run_understanding_check_tool(input_data: UnderstandingCheckInput) -> UnderstandingCheckOutput:
    system_prompt = (
        "Bạn là Quiz Generator Agent của VLearn. Nhiệm vụ của bạn là sinh 1 bài kiểm tra mức độ hiểu bài của học viên.\n"
        "Bạn có thể chọn 1 trong 2 định dạng:\n"
        "1. 'multiple_choice': Bài trắc nghiệm 4 lựa chọn.\n"
        "2. 'short_answer': Câu hỏi mở yêu cầu học viên tự gõ câu trả lời vào ô nhập.\n\n"
        "Trả về định dạng JSON duy nhất:\n"
        "{\n"
        "  \"quiz_type\": \"multiple_choice\" hoặc \"short_answer\",\n"
        "  \"concept\": \"<tên_khái_niệm>\",\n"
        "  \"question\": \"<câu_hỏi_kiểm_tra>\",\n"
        "  \"options\": [\"đáp án A\", \"đáp án B\", \"đáp án C\", \"đáp án D\"], // Nếu là multiple_choice\n"
        "  \"correct_index\": 1, // Nếu là multiple_choice (0 đến 3)\n"
        "  \"expected_keywords\": [\"từ_khóa_1\", \"từ_khóa_2\"], // Nếu là short_answer\n"
        "  \"explanation\": \"<lời_giải_thích_khi_trả_lời_đúng>\"\n"
        "}"
    )

    user_prompt = (
        f"Câu hỏi học viên: \"{input_data.question}\"\n"
        f"Tutor đã trả lời: \"{input_data.tutor_answer}\"\n"
        f"Trang slide: {input_data.page_number}"
    )

    result_json = call_gemini_json(user_prompt, system_instruction=system_prompt, api_key=input_data.api_key)

    if result_json and "question" in result_json:
        q_type = result_json.get("quiz_type", "short_answer")
        return UnderstandingCheckOutput(
            quiz_id=f"q_{int(time.time()*1000)}",
            quiz_type=q_type,
            concept=result_json.get("concept", "Kiểm tra hiểu bài"),
            question=result_json.get("question", "Hãy tóm tắt ngắn gọn khái niệm cốt lõi vừa học?"),
            options=result_json.get("options", []),
            correct_index=int(result_json.get("correct_index", 0)),
            expected_keywords=result_json.get("expected_keywords", ["JSON Schema", "Function Calling", "Context"]),
            explanation=result_json.get("explanation", "Xuất sắc! Bạn đã giải thích đúng bản chất khái niệm.")
        )

    # Fallback Quiz Generator (Alternates between multiple_choice & short_answer)
    page_num = input_data.page_number
    q_lower = input_data.question.lower()

    # If asking for explanation or how-to -> Generate Short Answer open question
    if "là gì" in q_lower or "giải thích" in q_lower or "thế nào" in q_lower:
        return UnderstandingCheckOutput(
            quiz_id=f"q_{int(time.time()*1000)}",
            quiz_type="short_answer",
            concept="Vận dụng Khái niệm Cốt lõi",
            question="Theo bạn, tại sao Function Calling lại được gọi là 'Hợp đồng' (Contract) giữa Agent và hệ thống bên ngoài? (Gõ 1-2 câu trả lời vào ô dưới):",
            expected_keywords=["schema", "hợp đồng", "cấu trúc", "json", "chính xác"],
            explanation="Chính xác! Function Calling cung cấp cấu trúc dữ liệu chuẩn hóa (JSON Schema), buộc Agent phải tuân thủ đúng định dạng parameters mà hệ thống yêu cầu."
        )

    return UnderstandingCheckOutput(
        quiz_id=f"q_{int(time.time()*1000)}",
        quiz_type="multiple_choice",
        concept="Function Calling Schema",
        question="Điểm khác biệt cốt lõi giữa Text-based ReAct và Function Calling là gì?",
        options=[
            "ReAct chạy nhanh hơn Function Calling",
            "Function Calling cung cấp JSON Schema chuẩn hóa cho mô hình thay vì tự đoán văn bản",
            "ReAct không dùng được cho các mô hình AI hiện đại",
            "Function Calling không cần định nghĩa công cụ trước khi gọi"
        ],
        correct_index=1,
        explanation="Chính xác! Function Calling giúp định nghĩa 'hợp đồng' dữ liệu rõ ràng dạng JSON Schema, giúp LLM trả ra đúng tham số hệ thống cần."
    )
