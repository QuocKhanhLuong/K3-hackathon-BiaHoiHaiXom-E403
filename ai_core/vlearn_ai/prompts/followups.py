"""Follow-up suggestion prompt definitions."""

FOLLOWUPS_SYSTEM_PROMPT = """Bạn là trợ lý VLearn. Hãy gợi ý từ 2 đến 3 câu hỏi đào sâu/mở rộng tiếp theo dựa trên bối cảnh bài học và câu trả lời vừa rồi.

Yêu cầu trả về đúng định dạng JSON tuân thủ schema FollowUpSuggestions:
{
  "followups": [
    {"label": "Nhãn ngắn 1", "question": "Nội dung câu hỏi gợi ý 1?"},
    {"label": "Nhãn ngắn 2", "question": "Nội dung câu hỏi gợi ý 2?"}
  ]
}
"""

FOLLOWUPS_USER_PROMPT_TEMPLATE = """Câu hỏi gốc:
<untrusted_student_query>
{user_query}
</untrusted_student_query>

Bối cảnh bài học:
<untrusted_course_context>
{selected_context}
</untrusted_course_context>

Giải thích vừa đưa ra:
{grounded_answer}
"""
