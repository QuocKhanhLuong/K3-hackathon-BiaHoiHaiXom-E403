"""
Tool: Clarification Tool (Powered by Gemini Flash 3.1 Lite / Gemini 3 Flash)
"""
import os
import sys

from pydantic import BaseModel

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from backend.gemini_client import call_gemini_json


class ClarificationInput(BaseModel):
    question: str
    page_number: int = 1
    api_key: str | None = None

class ClarificationOutput(BaseModel):
    clarifying_question: str
    suggested_inputs: list[str]

def run_clarification_tool(input_data: ClarificationInput) -> ClarificationOutput:
    system_prompt = (
        "Bạn là Clarification Agent của VLearn. Khi học viên đưa ra câu hỏi ngắn hoặc mơ hồ, "
        "hãy đặt 1 câu hỏi làm rõ thân thiện và đưa ra 3 phương án gợi ý ngắn để học viên bấm nhanh.\n"
        "Trả về JSON dạng:\n"
        "{\"clarifying_question\": \"...\", \"suggested_inputs\": [\"gợi ý 1\", \"gợi ý 2\", \"gợi ý 3\"]}"
    )

    user_prompt = f"Câu hỏi học viên: \"{input_data.question}\"\nTrang slide: {input_data.page_number}"

    result_json = call_gemini_json(user_prompt, system_instruction=system_prompt, api_key=input_data.api_key)

    if result_json and "clarifying_question" in result_json:
        return ClarificationOutput(
            clarifying_question=result_json.get("clarifying_question", f"Bạn muốn làm rõ góc độ nào trên Slide trang {input_data.page_number}?"),
            suggested_inputs=result_json.get("suggested_inputs", [
                "Giải thích theo ví dụ dự án thực tế",
                "So sánh với cách làm thông thường",
                "Hướng dẫn chi tiết các bước triển khai"
            ])
        )

    return ClarificationOutput(
        clarifying_question=f"Bạn muốn mình làm rõ hơn về khái niệm chung hay hướng dẫn áp dụng trực tiếp vào dự án Hackathon nhóm bạn trên Slide trang {input_data.page_number}?",
        suggested_inputs=[
            "Giải thích theo ví dụ dự án thực tế",
            "So sánh với cách làm thông thường",
            "Hướng dẫn chi tiết các bước triển khai"
        ]
    )
