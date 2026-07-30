"""
Tool: Misconception Detection & Re-explanation (Powered by Gemini Flash 3.1 Lite / Gemini 3 Flash)
"""
import os
import sys
import time

from pydantic import BaseModel

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from backend.gemini_client import call_gemini_json


class MisconceptionInput(BaseModel):
    question_text: str
    selected_option: int
    correct_option: int
    page_number: int = 1
    api_key: str | None = None

class RecheckQuiz(BaseModel):
    quiz_id: str
    concept: str
    question: str
    options: list[str]
    correct_index: int
    explanation: str

class MisconceptionOutput(BaseModel):
    misconception_point: str
    re_explanation: str
    new_example: str
    recheck_question: RecheckQuiz

def run_misconception_detection_tool(input_data: MisconceptionInput) -> MisconceptionOutput:
    system_prompt = (
        "Bạn là Misconception Detection Agent của VLearn. Học viên vừa chọn sai đáp án trong bài Quiz trắc nghiệm. "
        "Nhiệm vụ của bạn:\n"
        "1. Phân tích nguyên nhân nhầm lẫn tư duy cốt lõi của học viên (misconception_point).\n"
        "2. Giải thích lại trúng điểm sai (re_explanation). LƯU Ý: Tuyệt đối KHÔNG đưa ví dụ vào phần này.\n"
        "3. Đưa ra 1 ví dụ minh họa mới (new_example). BẮT BUỘC: Nội dung phần này phải hoàn toàn khác biệt với phần re_explanation, KHÔNG ĐƯỢC CHÉP LẠI (COPY) phần giải thích.\n"
        "4. Sinh 1 bài Quiz phụ 4 lựa chọn để kiểm tra lại (recheck_question).\n\n"
        "Trả về định dạng JSON duy nhất:\n"
        "{\n"
        "  \"misconception_point\": \"...\",\n"
        "  \"re_explanation\": \"...\",\n"
        "  \"new_example\": \"...\",\n"
        "  \"recheck_question\": {\n"
        "    \"quiz_id\": \"rq_1\",\n"
        "    \"concept\": \"...\",\n"
        "    \"question\": \"...\",\n"
        "    \"options\": [\"A\", \"B\", \"C\", \"D\"],\n"
        "    \"correct_index\": 1,\n"
        "    \"explanation\": \"...\"\n"
        "  }\n"
        "}"
    )

    user_prompt = (
        f"Câu hỏi Quiz: \"{input_data.question_text}\"\n"
        f"Lựa chọn của học viên: {input_data.selected_option} (Đáp án đúng: {input_data.correct_option})\n"
        f"Trang slide: {input_data.page_number}"
    )

    result_json = call_gemini_json(user_prompt, system_instruction=system_prompt, api_key=input_data.api_key)

    if result_json and "misconception_point" in result_json:
        recheck_data = result_json.get("recheck_question", {})
        recheck = RecheckQuiz(
            quiz_id=recheck_data.get("quiz_id", f"rq_{int(time.time()*1000)}"),
            concept=recheck_data.get("concept", "Kiểm tra lại qua ví dụ mới"),
            question=recheck_data.get("question", "Nếu slide cập nhật trang mới, làm sao để AI Tutor nắm được ngay?"),
            options=recheck_data.get("options", ["Retrain AI", "Nạp trang slide mới vào Context Window", "Thay đổi System Policy", "Không thể"]),
            correct_index=int(recheck_data.get("correct_index", 1)),
            explanation=recheck_data.get("explanation", "Rất xuất sắc! Bạn đã hiểu đúng bản chất.")
        )

        return MisconceptionOutput(
            misconception_point=result_json.get("misconception_point", "Phát hiện điểm nhầm lẫn tư duy."),
            re_explanation=result_json.get("re_explanation", "Giải thích lại khái niệm."),
            new_example=result_json.get("new_example", "Ví dụ minh họa mới."),
            recheck_question=recheck
        )

    # Fallback response
    recheck = RecheckQuiz(
        quiz_id=f"rq_{int(time.time()*1000)}",
        concept="Kiểm tra lại qua ví dụ mới",
        question="Nếu slide được cập nhật trang mới trong buổi học, bạn làm cách nào để AI Tutor cập nhật kiến thức ngay?",
        options=[
            "Huấn luyện lại (Retrain) toàn bộ mô hình AI",
            "Nạp trang slide mới vào Context Window khi gửi request API",
            "Thay đổi System Policy",
            "Không thể cập nhật được"
        ],
        correct_index=1,
        explanation="Rất xuất sắc! Bạn đã hiểu đúng bản chất của Context Window rồi!"
    )

    return MisconceptionOutput(
        misconception_point="Học viên đang nhầm lẫn giữa dữ liệu trong Context Window (được nạp động mỗi lượt) và tri thức lưu trong Weights tĩnh của LLM.",
        re_explanation="💡 **Điểm cần lưu ý:** Context Window chỉ chứa dữ liệu nạp tạm thời khi bạn gửi API request (gồm System prompt, Chat history, Slide text). Ngược lại, Weights là tri thức AI đã học cố định từ trước.",
        new_example="📌 **Ví dụ mới:** Giống như khi bạn đi thi được mang tài liệu vào phòng thi (Context Window), khác hoàn toàn với những gì bạn tự học thuộc trong đầu (Weights).",
        recheck_question=recheck
    )
