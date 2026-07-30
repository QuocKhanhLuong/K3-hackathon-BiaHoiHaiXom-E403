"""
Tool: Follow-up Suggestions Tool (Mặc định 3 câu hỏi gợi ý đào sâu trước khi kết thúc lượt)
"""
from pydantic import BaseModel
from typing import List, Optional
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from backend.gemini_client import call_gemini_json

class FollowupInput(BaseModel):
    tutor_answer: str
    page_number: int = 1
    api_key: Optional[str] = None

class FollowupOutput(BaseModel):
    suggestions: List[str]

def run_followup_suggestions_tool(input_data: FollowupInput) -> FollowupOutput:
    system_prompt = (
        "Bạn là Follow-up Suggestion Agent của VLearn. Nhiệm vụ của bạn là tạo đúng 3 câu hỏi gợi ý đào sâu "
        "ngắn gọn, hấp dẫn giúp học viên chủ động mở rộng kiến thức trước khi kết thúc lượt.\n"
        "Trả về định dạng JSON duy nhất:\n"
        "{\"suggestions\": [\"câu hỏi 1\", \"câu hỏi 2\", \"câu hỏi 3\"]}"
    )

    user_prompt = f"Phản hồi vừa qua của Tutor: \"{input_data.tutor_answer}\"\nTrang slide: {input_data.page_number}"

    result_json = call_gemini_json(user_prompt, system_instruction=system_prompt, api_key=input_data.api_key)

    if result_json and "suggestions" in result_json and isinstance(result_json["suggestions"], list):
        if len(result_json["suggestions"]) >= 3:
            return FollowupOutput(suggestions=result_json["suggestions"][:3])

    page_num = input_data.page_number
    if page_num == 4:
        suggestions = [
            "Ví dụ JSON Schema chuẩn khi định nghĩa 1 tool tra cứu tài liệu?",
            "Khi mô hình gọi sai tên Tool thì xử lý fallback ra sao?",
            "Cách test nghiệm thu Function Calling trong bài Hackathon?"
        ]
    elif page_num == 5:
        suggestions = [
            "Cách tính toán Token Budget allocation cho 1 hội thoại kéo dài 20 lượt?",
            "Kỹ thuật cắt tỉa (pruning) chat history khi vọt context limit?",
            "So sánh giữa RAG vector search và nạp nguyên file slide vào context?"
        ]
    else:
        suggestions = [
            "Làm sao áp dụng khái niệm này vào bài thi Hackathon nhóm mình?",
            "Các lỗi phổ biến học viên hay gặp khi triển khai phần này là gì?",
            "Ví dụ 1 kịch bản fail tiêu biểu và cách khắc phục?"
        ]

    return FollowupOutput(suggestions=suggestions)
