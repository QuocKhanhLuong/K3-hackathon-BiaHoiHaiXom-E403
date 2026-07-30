"""
Tool: Grounded Answer Generator (Supports Deep-dive Knowledge Expansion)
"""
from pydantic import BaseModel
from typing import List, Optional
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from backend.gemini_client import call_gemini

SLIDE_KNOWLEDGE = [
    {
        "page": 1,
        "title": "AI Product Thinking & Requirements",
        "course": "COMP2010 · Lecture_material_ms204v3b_r9mo78",
        "subtitle": "AICB-P1 · Ngày 5 · Build agent xong, nhưng sản phẩm cho ai?",
        "content": "Tên Giảng Viên: VinUniversity Phase 1 Tuần 1. Giới thiệu tổng quan về tư duy thiết kế sản phẩm AI cho người dùng thật. Không dừng lại ở prototype kỹ thuật mà tập trung vào giá trị cho end-user.",
        "key_concepts": ["AI Product Thinking", "End-user value", "Problem alignment"]
    },
    {
        "page": 2,
        "title": "HÃY SUY NGHĨ: Bạn đã build xong Agent chưa?",
        "content": "Nhiều đội nhóm tập trung 90% thời gian gọi API và chỉnh prompt, nhưng quên mất người dùng gặp vấn đề gì. Bài toán sản phẩm AI đòi hỏi bằng chứng thực tế từ khảo sát hoặc data mining.",
        "key_concepts": ["Build vs Problem", "Evidence gathering", "Data mining"]
    },
    {
        "page": 3,
        "title": "Khung Xác định Bài toán & Chỗ khó (Taxonomy)",
        "content": "4 lớp chỗ khó cần thiết kế: (1) Nguồn sự thật - Grounding, (2) Mơ hồ/Thiếu thông tin - Ambiguity, (3) Thẩm quyền & Phạm vi - Boundary, (4) Đặc thù Domain - Domain Risk.",
        "key_concepts": ["Taxonomy", "4 lớp chỗ khó", "Grounding", "Boundary"]
    },
    {
        "page": 4,
        "title": "Function Calling & Agent Tools Contract",
        "content": "Text-based ReAct vs Structured Function Calling. Function Calling cung cấp hợp đồng rõ ràng (JSON schema) giúp Agent thực thi hành động chính xác thay vì chỉ sinh văn bản.",
        "key_concepts": ["Function Calling", "JSON Schema", "ReAct", "Agent Tools"]
    },
    {
        "page": 5,
        "title": "Quản lý Ngữ cảnh (Context Management)",
        "content": "Context bao gồm System policy, History, Current input, Tool schemas, Output buffer. Token budget allocation là yếu tố quyết định để tránh vọt chi phí và quá tải cửa sổ ngữ cảnh.",
        "key_concepts": ["Context Management", "Token Budget Allocation", "System Policy"]
    }
]

class GroundedAnswerInput(BaseModel):
    question: str
    selected_text: Optional[str] = ""
    page_number: int = 1
    is_deep_dive: bool = False
    api_key: Optional[str] = None

class GroundedAnswerOutput(BaseModel):
    answer: str
    citations: List[int]
    page_number: int
    model_used: str

def run_grounded_answer_tool(input_data: GroundedAnswerInput) -> GroundedAnswerOutput:
    page_num = input_data.page_number
    slide = next((s for s in SLIDE_KNOWLEDGE if s["page"] == page_num), SLIDE_KNOWLEDGE[0])
    
    deep_instruction = ""
    if input_data.is_deep_dive:
        deep_instruction = " ĐẶC BIỆT: Hãy thêm 1 mục '**🚀 Mở rộng tri thức (Deep-dive Expansion):**' để phân tích chuyên sâu ứng dụng thực tế hoặc trường hợp nâng cao cho học viên."

    system_prompt = (
        "Bạn là VLearn AI Tutor của VinUniversity. Nhiệm vụ của bạn là giải thích bài học cho học viên "
        "dựa trên căn cứ tài liệu slide bài giảng được cung cấp. Bắt buộc kèm mã trích dẫn [trang N] ở cuối các ý chính. "
        "Nếu tài liệu không chứa thông tin (như nộp bài ở đâu, link colab, tải slide), hãy giải thích lịch sự "
        "và hướng dẫn xem thông báo trên Discord/Canvas khóa học." + deep_instruction
    )

    user_prompt = (
        f"Ngữ cảnh Slide Trang {slide['page']} (Tiêu đề: '{slide['title']}'):\n"
        f"Nội dung slide: \"{slide['content']}\"\n"
        f"Đoạn văn học viên bôi đen trên slide: \"{input_data.selected_text or 'Không có'}\"\n"
        f"Câu hỏi của học viên: \"{input_data.question}\"\n\n"
        f"Hãy trả lời câu hỏi một cách chuẩn xác, ngắn gọn và thân thiện."
    )

    llm_response = call_gemini(user_prompt, system_instruction=system_prompt, api_key=input_data.api_key)

    if llm_response:
        citations = [slide["page"]] if f"[trang {slide['page']}]" in llm_response or "bài tập" not in input_data.question.lower() else []
        return GroundedAnswerOutput(
            answer=llm_response,
            citations=citations,
            page_number=page_num,
            model_used="gemini-3.1-flash-lite"
        )

    # Fallback response
    query_lower = (input_data.question + " " + (input_data.selected_text or "")).lower()
    citations = [slide["page"]]

    if any(k in query_lower for k in ["bài tập", "nộp", "deadline"]):
        answer = f"Rất tiếc, tài liệu slide trang {slide['page']} không chứa thông tin quy trình nộp bài. Bạn vui lòng kiểm tra trên trang chủ LMS hoặc kênh Discord chính thức của khóa học."
        citations = []
    elif any(k in query_lower for k in ["context", "ngữ cảnh"]):
        answer = "Theo slide trang 5, Quản lý Ngữ cảnh (Context Management) là việc phân bổ token budget cho 5 thành phần: System policy, Lịch sử đối thoại, Input hiện tại, Tool schemas và Output buffer [trang 5]."
        if input_data.is_deep_dive:
            answer += "\n\n🚀 **Mở rộng tri thức (Deep-dive Expansion):** Trong các ứng dụng Agent thực tế, kỹ thuật Context Pruning (cắt tỉa lịch sử) và RAG Hybrid Search thường được sử dụng kết hợp để duy trì Token budget dưới 4,000 tokens."
        citations = [5]
    elif any(k in query_lower for k in ["function calling", "tool"]):
        answer = "Theo trang 4, Function Calling ra đời cung cấp một \"Hợp đồng\" rõ ràng dạng JSON Schema cho Agent. Thay vì tự đoán câu lệnh text, Agent trả về cấu trúc dữ liệu chuẩn để hệ thống thực thi chính xác [trang 4]."
        if input_data.is_deep_dive:
            answer += "\n\n🚀 **Mở rộng tri thức (Deep-dive Expansion):** Việc định nghĩa strict JSON Schema giúp loại bỏ hoàn toàn lỗi SyntaxError khi parser kết quả từ LLM, đồng thời hỗ trợ validation tự động trước khi gọi API thật."
        citations = [4]
    else:
        answer = f"Dựa trên nội dung Slide trang {slide['page']} (\"{slide['title']}\"): {slide['content']} [trang {slide['page']}]."
        if input_data.is_deep_dive:
            answer += f"\n\n🚀 **Mở rộng tri thức (Deep-dive Expansion):** Phân tích góc nhìn thực tế khi áp dụng bài học trang {slide['page']} vào dự án Hackathon nhóm."

    return GroundedAnswerOutput(
        answer=answer,
        citations=citations,
        page_number=page_num,
        model_used="gemini-3.1-flash-lite (fallback)"
    )
