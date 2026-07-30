# VLearn Tutor UI Prototype

Prototype nằm trong `codebase/` và có thể chạy bằng cách mở trực tiếp:

```text
codebase/index.html
```

Workflow đã mock:

1. User nhập câu hỏi vào ô chat và bấm gửi hoặc nhấn Enter.
2. Tutor trả lời theo dữ liệu giả, có citation dạng `[2]`, `[3]`, `[4]`, `[5]`.
3. Follow-up suggestions được gắn ngay bên dưới từng output của chatbot, nên mỗi lượt trả lời giữ các gợi ý riêng của lượt đó.
4. User có 2 cách đi tiếp:
   - Gõ câu hỏi mới vào ô chat.
   - Bấm một follow-up question để chatbot tự đưa câu đó thành lượt hỏi mới và trả lời tương ứng.
5. Khi bấm citation, viewer bên trái nhảy tới slide tương ứng và highlight slide.
6. Mock-adapter trong `codebase/mock-adapter.js` điều phối theo flow:
   - Học viên chọn đoạn và hỏi.
   - Tutor trả lời có căn cứ.
   - Learning Loop Orchestrator phân nhánh.
   - Câu hỏi đơn giản: kết thúc lượt.
   - Thiếu thông tin: hỏi làm rõ rồi chuyển sang kiểm tra hiểu.
     - Loại 1: multiple choice để học viên bấm chọn nhanh.
     - Loại 2: yêu cầu học viên nhập thêm ngữ cảnh trực tiếp trong ô chat.
   - Cần kiểm tra hiểu: đưa understanding check.
     - Option quiz được chọn trực tiếp dưới output; đáp án đúng hiện tick, đáp án sai hiện giải thích tại sao sai.
   - Trả lời sai: phát hiện misconception, giải thích lại và check bằng ví dụ mới.
   - Có thể đào sâu: đưa follow-up suggestions.

Các nội dung hiện đang là mock để demo UI/workflow, chưa nối API hoặc retrieval thật.

Gợi ý demo nhánh hỏi làm rõ:

- Nhập `cái này` hoặc `phần này` để xem loại multiple choice.
- Nhập `giải thích` để xem loại yêu cầu học viên nhập thêm đáp án/ngữ cảnh trong ô chat.
