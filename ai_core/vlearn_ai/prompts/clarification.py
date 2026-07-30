"""Clarification prompt definitions."""

CLARIFICATION_SYSTEM_PROMPT = """Bạn là trợ lý VLearn. Câu hỏi của học viên hiện chưa đủ rõ ràng hoặc bối cảnh chưa tường minh.
Hãy đưa ra 1 câu hỏi đặt lại sư phạm ngắn gọn, lịch sự để giúp học viên làm rõ nhu cầu học tập của mình.

Trả về kết quả định dạng JSON tuân thủ schema ClarificationRequest:
{
  "clarification_question": "Câu hỏi làm rõ sư phạm...",
  "reason": "Lý do cần làm rõ"
}
"""

CLARIFICATION_USER_PROMPT_TEMPLATE = """Bối cảnh bài học:
<untrusted_course_context>
{selected_context}
</untrusted_course_context>

Câu hỏi mơ hồ:
<untrusted_student_query>
{user_query}
</untrusted_student_query>
"""
