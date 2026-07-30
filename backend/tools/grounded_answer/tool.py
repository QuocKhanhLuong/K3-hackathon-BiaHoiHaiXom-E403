"""
Tool: Grounded Answer Generator
Uses actual PDF slide contents from data/vlearn-pack/slides/ (d1-slide-hackathon.pdf & d2-slide-hackathon.pdf)
"""
from pydantic import BaseModel
from typing import List, Optional
import sys
import os
import re

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


def _deck_slides_for_page(page_num: int) -> List[dict]:
    current = next((s for s in ALL_PDF_SLIDES if s["page"] == page_num), None)
    if not current:
        return ALL_PDF_SLIDES
    return [s for s in ALL_PDF_SLIDES if s.get("deck_id") == current.get("deck_id")]


def _slides_for_question(question: str, page_num: int) -> List[dict]:
    """Resolve every slide explicitly or relatively requested by the learner."""
    question_lower = question.lower()
    deck_slides = _deck_slides_for_page(page_num)
    by_page = {slide["page"]: slide for slide in ALL_PDF_SLIDES}

    # Explicit range: "trang 1-5", "trang 1 đến 5", "pages 1 to 5".
    range_match = re.search(r"(?:trang|pages?)\s*(\d+)\s*(?:-|–|—|đến|tới|to)\s*(\d+)", question_lower)
    if range_match:
        start, end = sorted((int(range_match.group(1)), int(range_match.group(2))))
        return [by_page[p] for p in range(start, end + 1) if p in by_page]

    # Explicit list: "trang 1, 2, 3 và 5".
    list_match = re.search(r"(?:trang|pages?)\s*((?:\d+\s*(?:,|;|và|&|\s)\s*)+\d+)", question_lower)
    if list_match:
        page_numbers = [int(value) for value in re.findall(r"\d+", list_match.group(1))]
        selected = [by_page[p] for p in dict.fromkeys(page_numbers) if p in by_page]
        if len(selected) > 1:
            return selected

    # Relative multi-page request. Without a direction, use the N-page window
    # ending at the page currently being read (e.g. page 5 => pages 1..5).
    count_match = re.search(r"(\d+)\s*(?:trang|pages?)", question_lower)
    multi_page_intent = any(term in question_lower for term in (
        "tóm tắt", "tổng hợp", "so sánh", "liên tiếp", "gần đây", "trước", "tiếp theo", "kế tiếp"
    ))
    if count_match and multi_page_intent:
        count = max(1, min(int(count_match.group(1)), 20))
        current_index = next((i for i, slide in enumerate(deck_slides) if slide["page"] == page_num), 0)
        if any(term in question_lower for term in ("tiếp theo", "kế tiếp", "sau đây")):
            start_index = current_index
        else:
            start_index = max(0, current_index - count + 1)
        return deck_slides[start_index:start_index + count]

    current = by_page.get(page_num)
    return [current] if current else (ALL_PDF_SLIDES[:1] or [])

def run_grounded_answer_tool(input_data: GroundedAnswerInput) -> GroundedAnswerOutput:
    page_num = input_data.page_number
    fallback_slide = ALL_PDF_SLIDES[0] if ALL_PDF_SLIDES else {
        "page": 1,
        "title": "AI IN ACTION Slide",
        "raw_text": "AI & LLM Foundation",
        "deck_name": "d1-slide-hackathon.pdf"
    }
    source_slides = _slides_for_question(input_data.question, page_num) or [fallback_slide]
    slide = source_slides[-1]
    citations = [source["page"] for source in source_slides]
    context_blocks = "\n\n".join(
        f"--- TRANG {source['page']} · {source.get('title', '')} ---\n"
        f"{source.get('raw_text', source.get('content', ''))}"
        for source in source_slides
    )
    citation_instruction = ", ".join(f"[trang {page}]" for page in citations)
    
    deep_instruction = ""
    if input_data.is_deep_dive:
        deep_instruction = " ĐẶC BIỆT: Hãy thêm 1 mục '**🚀 Mở rộng tri thức (Deep-dive Expansion):**' để phân tích chuyên sâu ứng dụng thực tế hoặc trường hợp nâng cao cho học viên."

    system_prompt = (
        f"Bạn là VLearn AI Tutor của VinUniversity. Bạn đang hỗ trợ học viên học slide '{slide.get('deck_name', 'Slide Hackathon')}'. "
        "Nhiệm vụ của bạn là giải thích bài học cho học viên dựa trên căn cứ tài liệu slide bài giảng được cung cấp bên dưới. "
        f"Các nguồn được cấp cho câu hỏi này là: {citation_instruction}. "
        "Bắt buộc trích dẫn đúng [trang N] ngay sau ý lấy từ trang đó; nếu tổng hợp nhiều trang, phải sử dụng đủ các trang nguồn liên quan. "
        "Nếu tài liệu không chứa thông tin (như nộp bài ở đâu, link colab, tải slide), hãy giải thích lịch sự "
        "và hướng dẫn xem thông báo trên Discord/Canvas khóa học." + deep_instruction
    )

    user_prompt = (
        f"Ngữ cảnh gồm {len(source_slides)} trang slide:\n"
        f"\"\"\"\n{context_blocks}\n\"\"\"\n"
        f"Đoạn văn học viên bôi đen trên slide: \"{input_data.selected_text or 'Không có'}\"\n"
        f"Câu hỏi của học viên: \"{input_data.question}\"\n\n"
        f"Hãy trả lời câu hỏi một cách chuẩn xác, ngắn gọn và thân thiện."
    )

    llm_response = call_gemini(user_prompt, system_instruction=system_prompt, api_key=input_data.api_key)

    if llm_response:
        if "bài tập" in input_data.question.lower() and not any(f"[trang {page}]" in llm_response for page in citations):
            citations = []
        return GroundedAnswerOutput(
            answer=llm_response,
            citations=citations,
            page_number=page_num,
            model_used="gemini-3.1-flash-lite"
        )

    # Fallback response grounded in real PDF content
    query_lower = (input_data.question + " " + (input_data.selected_text or "")).lower()
    if any(k in query_lower for k in ["bài tập", "nộp", "deadline"]):
        answer = f"Rất tiếc, tài liệu slide trang {slide['page']} (tệp {slide.get('deck_name', 'PDF')}) không chứa thông tin quy trình nộp bài. Bạn vui lòng kiểm tra trên trang chủ LMS hoặc kênh Discord chính thức của khóa học."
        citations = []
    else:
        summaries = []
        for source in source_slides:
            excerpt = source.get('raw_text', source.get('content', ''))[:220]
            summaries.append(f"**Trang {source['page']} — {source.get('title', '')}:** {excerpt}... [trang {source['page']}]")
        answer = "Dựa trên các slide được yêu cầu:\n\n" + "\n\n".join(summaries)
        if input_data.is_deep_dive:
            answer += f"\n\n🚀 **Mở rộng tri thức (Deep-dive Expansion):** Hãy kết nối các ý trên vào dự án Hackathon nhóm. {citation_instruction}."

    return GroundedAnswerOutput(
        answer=answer,
        citations=citations,
        page_number=page_num,
        model_used="gemini-3.1-flash-lite (fallback)"
    )
