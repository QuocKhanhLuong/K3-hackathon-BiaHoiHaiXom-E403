"""
Tool: Learning Loop Orchestrator Master Agent (Powered by Gemini Flash 3.1 Lite / Gemini 3 Flash)
"""
import os
import sys

from pydantic import BaseModel

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from backend.gemini_client import call_gemini_json


class OrchestratorInput(BaseModel):
    question: str
    tutor_answer: str
    chat_history: list[dict] | None = []
    api_key: str | None = None

class OrchestratorOutput(BaseModel):
    branch: str  # "simple_end" | "clarify" | "understanding_check" | "followup"
    title: str
    description: str
    next_node: str
    model_used: str

def run_orchestrator_tool(input_data: OrchestratorInput) -> OrchestratorOutput:
    system_prompt = (
        "Bạn là Master Agent 'Bước tiếp theo?' trong sơ đồ điều phối sư phạm VLearn Learning Loop Orchestrator. "
        "Nhiệm vụ của bạn là phân tích câu hỏi của học viên và phản hồi của Tutor, sau đó quyết định 1 trong 4 nhánh sư phạm:\n"
        "- 'simple_end': Câu hỏi thông tin đơn giản đã giải đáp xong -> Kết thúc lượt (đính kèm 3 gợi ý đào sâu).\n"
        "- 'clarify': Câu hỏi bị ngắn, mơ hồ, thiếu thông tin -> Cần hỏi làm rõ.\n"
        "- 'understanding_check': Khái niệm phức tạp (Function Calling, Context, Taxonomy) -> Cần kiểm tra hiểu bài bằng Quiz.\n"
        "- 'followup': Câu hỏi có thể đào sâu -> Mở rộng tri thức trực tiếp trong phản hồi LLM và sau đó trỏ vào gọi Understanding Check.\n\n"
        "Trả về định dạng JSON duy nhất:\n"
        "{\"branch\": \"<branch_code>\", \"title\": \"<tên_nhánh>\", \"description\": \"<lý_do_rẽ_nhánh>\", \"next_node\": \"<tên_tool_tiếp_theo>\"}"
    )

    user_prompt = (
        f"Câu hỏi học viên: \"{input_data.question}\"\n"
        f"Phản hồi Tutor: \"{input_data.tutor_answer}\"\n"
        f"Hãy chọn nhánh sư phạm phù hợp nhất."
    )

    result_json = call_gemini_json(user_prompt, system_instruction=system_prompt, api_key=input_data.api_key)

    if result_json and "branch" in result_json:
        branch_code = result_json.get("branch", "understanding_check")
        
        if branch_code == "followup":
            return OrchestratorOutput(
                branch="followup",
                title="Có thể đào sâu → Mở rộng tri thức",
                description="Mở rộng tri thức trực tiếp trong câu trả lời LLM và chuyển tiếp sang Understanding Check.",
                next_node="Mở rộng tri thức → Understanding Check",
                model_used="gemini-3.1-flash-lite"
            )

        return OrchestratorOutput(
            branch=branch_code,
            title=result_json.get("title", "Cần kiểm tra hiểu"),
            description=result_json.get("description", "Phân tích bởi Gemini 3.1 Flash Lite"),
            next_node=result_json.get("next_node", "Understanding Check"),
            model_used="gemini-3.1-flash-lite"
        )

    # Rule-based fallback decision
    q_lower = input_data.question.lower()
    if len(q_lower.split()) < 3 or any(k in q_lower for k in ["là sao", "chưa rõ", "này là gì"]):
        return OrchestratorOutput(
            branch="clarify",
            title="Thiếu thông tin",
            description="Câu hỏi của học viên còn ngắn hoặc chưa rõ ngữ cảnh cụ thể.",
            next_node="Hỏi làm rõ",
            model_used="gemini-3.1-flash-lite (fallback)"
        )

    if any(k in q_lower for k in ["như thế nào", "tại sao", "phân biệt", "ngữ cảnh", "function calling", "chỗ khó"]):
        return OrchestratorOutput(
            branch="understanding_check",
            title="Cần kiểm tra hiểu",
            description="Khái niệm vừa trao đổi có độ phức tạp cao, kích hoạt Tool Understanding Check tạo Quiz trắc nghiệm.",
            next_node="Understanding Check",
            model_used="gemini-3.1-flash-lite (fallback)"
        )

    if any(k in q_lower for k in ["ví dụ", "ứng dụng", "thực tế", "build", "mở rộng"]):
        return OrchestratorOutput(
            branch="followup",
            title="Có thể đào sâu → Mở rộng tri thức",
            description="Mở rộng tri thức trực tiếp trong câu trả lời LLM và chuyển tiếp sang Understanding Check.",
            next_node="Mở rộng tri thức → Understanding Check",
            model_used="gemini-3.1-flash-lite (fallback)"
        )

    return OrchestratorOutput(
        branch="simple_end",
        title="Câu hỏi đơn giản",
        description="Câu hỏi thông tin trực tiếp đã được giải đáp đầy đủ.",
        next_node="Kết thúc lượt",
        model_used="gemini-3.1-flash-lite (fallback)"
    )
