"""
Tool: Grounded Answer Generator
Uses actual PDF slide contents from data/vlearn-pack/slides/ (d1-slide-hackathon.pdf & d2-slide-hackathon.pdf)
"""
from pydantic import BaseModel
from typing import List, Optional
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from backend.gemini_client import call_gemini
from backend.slide_loader import ALL_PDF_SLIDES

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
    slide = next((s for s in ALL_PDF_SLIDES if s["page"] == page_num), ALL_PDF_SLIDES[0] if ALL_PDF_SLIDES else {
        "page": 1,
        "title": "AI IN ACTION Slide",
        "raw_text": "AI & LLM Foundation",
        "deck_name": "d1-slide-hackathon.pdf"
    })
    
    deep_instruction = ""
    if input_data.is_deep_dive:
        deep_instruction = " ĐẶC BIỆT: Hãy thêm 1 mục '**🚀 Mở rộng tri thức (Deep-dive Expansion):**' để phân tích chuyên sâu ứng dụng thực tế hoặc trường hợp nâng cao cho học viên."

    system_prompt = (
        f"Bạn là VLearn AI Tutor của VinUniversity. Bạn đang hỗ trợ học viên học slide '{slide.get('deck_name', 'Slide Hackathon')}'. "
        "Nhiệm vụ của bạn là giải thích bài học cho học viên dựa trên căn cứ tài liệu slide bài giảng được cung cấp bên dưới. "
        "Bắt buộc kèm mã trích dẫn [trang N] ở cuối các ý chính. "
        "Nếu tài liệu không chứa thông tin (như nộp bài ở đâu, link colab, tải slide), hãy giải thích lịch sự "
        "và hướng dẫn xem thông báo trên Discord/Canvas khóa học." + deep_instruction
    )

    user_prompt = (
        f"Ngữ cảnh Slide Trang {slide['page']} (Tiêu đề: '{slide['title']}'):\n"
        f"Nội dung slide chi tiết:\n\"\"\"\n{slide.get('raw_text', slide.get('content', ''))}\n\"\"\"\n"
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

    # Fallback response grounded in real PDF content
    query_lower = (input_data.question + " " + (input_data.selected_text or "")).lower()
    citations = [slide["page"]]

    if any(k in query_lower for k in ["bài tập", "nộp", "deadline"]):
        answer = f"Rất tiếc, tài liệu slide trang {slide['page']} (tệp {slide.get('deck_name', 'PDF')}) không chứa thông tin quy trình nộp bài. Bạn vui lòng kiểm tra trên trang chủ LMS hoặc kênh Discord chính thức của khóa học."
        citations = []
    else:
        answer = f"Dựa trên nội dung Slide trang {slide['page']} ({slide.get('deck_name', 'PDF')} — \"{slide['title']}\"): {slide.get('raw_text', slide.get('content', ''))[:300]}... [trang {slide['page']}]."
        if input_data.is_deep_dive:
            answer += f"\n\n🚀 **Mở rộng tri thức (Deep-dive Expansion):** Phân tích góc nhìn thực tế khi áp dụng bài học trang {slide['page']} vào dự án Hackathon nhóm."

    return GroundedAnswerOutput(
        answer=answer,
        citations=citations,
        page_number=page_num,
        model_used="gemini-3.1-flash-lite (fallback)"
    )
