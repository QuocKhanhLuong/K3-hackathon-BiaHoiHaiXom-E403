"""Prompt contract for one-shot factual grounding repair."""

GROUNDING_REPAIR_PROMPT_VERSION = "2.0.0"
GROUNDING_REPAIR_PROMPT = """Bạn đang sửa một GroundedAnswer đã không qua kiểm tra grounding.
Chỉ sửa cấu trúc grounding; chỉ dùng course context được cung cấp và không thêm nội dung sự thật mới.
Giữ đúng ý định của original user_query. Không thay câu trả lời không được hỗ trợ bằng một sự thật dễ hơn nhưng không liên quan.
Giữ ý nghĩa ngắn gọn ban đầu nếu có thể chứng minh; xóa mọi câu sự thật không có bằng chứng. Nếu ý định không thể được hỗ trợ, trả về answerability="insufficient_context", claims=[], citations=[].
Mỗi câu sự thật còn lại trong answer phải có GroundedClaim tương ứng.
Mỗi claim phải tham chiếu citation có trong chính output.
citation_id phải khớp chính xác source_id trong header [source source_id="..."]; không tạo hay thêm hậu tố ID.
snippet phải được sao chép nguyên văn từ source tương ứng.
Trả về duy nhất GroundedAnswer theo structured schema.
"""
