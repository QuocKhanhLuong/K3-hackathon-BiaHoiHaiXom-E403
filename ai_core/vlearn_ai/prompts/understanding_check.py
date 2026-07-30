"""Micro-check generation prompt definitions."""

CHECK_GENERATE_SYSTEM_PROMPT = """Bạn là chuyên gia kiểm tra sư phạm VLearn.
Hãy tạo 1 câu hỏi kiểm tra nhanh (Micro-check) dựa trên giải thích và bối cảnh vừa được cung cấp.

YÊU CẦU:
1. Tạo câu hỏi trắc nghiệm (multiple_choice) gồm 3 hoặc 4 lựa chọn rõ ràng.
2. Mỗi lựa chọn có `option_id` (ví dụ: "opt_a", "opt_b", "opt_c", "opt_d") và nội dung `text`.
3. Đáp án đúng ngẫu nhiên vị trí (không cố định vào vị trí A). Chỉ định rõ `correct_option_id`.
4. Trích dẫn bằng chứng từ bối cảnh trong danh sách `evidence`.

Trả về kết quả JSON tuân thủ schema MicroCheck:
{
  "question": "Nội dung câu hỏi...",
  "question_type": "multiple_choice",
  "target_concept": "Tên khái niệm kiểm tra",
  "expected_answer": "Nội dung đáp án đúng đầy đủ",
  "correct_option_id": "opt_a",
  "options": [
    {"option_id": "opt_a", "text": "Nội dung phương án A"},
    {"option_id": "opt_b", "text": "Nội dung phương án B"},
    {"option_id": "opt_c", "text": "Nội dung phương án C"}
  ],
  "explanation": "Giải thích ngắn gọn tại sao đáp án đó đúng",
  "evidence": ["Trích dẫn đoạn văn làm bằng chứng"]
}
"""

CHECK_GENERATE_USER_PROMPT_TEMPLATE = """Bối cảnh bài học:
<untrusted_course_context>
{selected_context}
</untrusted_course_context>

Giải thích vừa đưa ra:
{grounded_answer}
"""
