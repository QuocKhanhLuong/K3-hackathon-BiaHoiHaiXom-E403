"""Router prompt definitions for classifying learner query workflow route."""

ROUTER_PROMPT_VERSION = "1.0.0"

ROUTER_SYSTEM_PROMPT = """Phân loại câu hỏi của học viên vào 1 trong 4 tuyến (route):

1. simple: Câu hỏi định nghĩa đơn giản, ngắn gọn hoặc tra cứu sự thật trực tiếp. (Ví dụ: "Key là gì?", "Softmax dùng để làm gì?")
2. clarify: Câu hỏi hoặc ngữ cảnh được chọn còn mơ hồ, thiếu thông tin rõ ràng. (Ví dụ: "Cái này hoạt động như thế nào?", "Tại sao lại làm vậy?" khi chưa rõ "cái này" là gì)
3. check: Câu hỏi về khái niệm cốt lõi, so sánh hoặc mối quan hệ giữa các thành phần cần tạo một câu hỏi kiểm tra nhanh (micro-check) mức độ hiểu. (Ví dụ: "Key và Value khác nhau như thế nào?")
4. deep: Câu hỏi giải thích lý do chuyên sâu, cơ chế nâng cao hoặc học viên đã hiểu khái niệm cơ bản và muốn đào sâu. (Ví dụ: "Tại sao attention phải chia cho căn bậc hai của d_k?")

Đầu ra phải là một đối tượng JSON cấu trúc phù hợp với RouteOutput.
"""

ROUTER_USER_PROMPT_TEMPLATE = """<untrusted_course_context>
{selected_context}
</untrusted_course_context>

<untrusted_student_query>
{user_query}
</untrusted_student_query>
"""
