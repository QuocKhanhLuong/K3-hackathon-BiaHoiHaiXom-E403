# Đề bài — Track duy nhất: "AI cho khoá AI Thực Chiến"

**Bối cảnh.** Khoá đang vận hành các sản phẩm AI nội bộ phục vụ ~1.000 học viên. Nhóm bạn là product team: chọn một hướng, tìm pain có bằng chứng, và build prototype **một tính năng**.

## Chọn 1 trong 3 hướng

### Hướng A — VLearn
Nền tảng học tập thích ứng của khoá; có AI tutor trong trang học (bôi đen đoạn tài liệu + hỏi, tutor trả lời kèm trích dẫn [trang N]).
- **Tối ưu AI tutor hiện có** — mining chatlog để tìm điểm tutor đang làm chưa tốt, chọn một điểm và cải thiện đến nơi đến chốn.
- **Tính năng AI mới trên VLearn** *(ví dụ cảm cỡ)*: kiểm tra hiểu thật cuối buổi · trải nghiệm học online · bản đồ lỗ hổng của lớp cho giảng viên từ signal, chatlog...

### Hướng B — Trợ lý Học viên (Discord)
Trợ lý trả lời câu hỏi học viên trong Discord khoá.
- **Tối ưu**: nhận diện intent thật (chào hỏi / hỏi bài / hỏi logistics) và trả lời đúng cỡ · biết-mình-không-biết + chuyển TA thay vì đoán · trả lời câu hỏi logistics (deadline, link, nộp bài) chỉ từ nguồn chính thức — trả lời sai deadline gây hậu quả trực tiếp cho học viên.
- **Tính năng mới**: bản tin cuối ngày cho TA (câu hỏi tồn, chủ đề hỏi nhiều nhất) · phát hiện học viên stuck và chủ động hỗ trợ — chủ động đến đâu thì thành phiền?

### Hướng C — Làn mở
Mining data và đề xuất sản phẩm AI khác cho khoá — qua đủ 5 tiêu chí nghiệm thu như mọi hướng.

## Data cấp cho mọi nhóm

Chatlog VLearn tutor × học viên đã ẩn danh + **6 transcript bài giảng bản sạch có mã đoạn để trích dẫn** + **2 bộ slide bài giảng bản hackathon** (xem `data/vlearn-pack/`). Với Trợ lý Học viên: không có data pack riêng — nhóm **tự tìm kiếm và quan sát trực tiếp trong Discord khoá** (đây cũng là một bài tập mining thực tế). **Cả lớp là người dùng thật** — nhóm có thể khảo sát 20 người ngay trong giờ nghỉ.

## Lát cắt = MỘT CÂU

> **một người dùng · một công việc · một quyết định AI · một kết quả**

## Ràng buộc chung

1. Build **prototype** (Sketch / Mock / Working) — mức nào cũng phải có **≥1 lời gọi AI chạy thật**. Không yêu cầu product hoàn chỉnh, không yêu cầu deploy.
2. Tự xác định **4 lớp chỗ khó** theo taxonomy — duyệt tại các mốc theo `04-rubric.md`:
   - ① **Nguồn sự thật** — chỗ nào AI bịa được? Không có căn cứ thì làm gì?
   - ② **Mơ hồ / thiếu thông tin** — input không đủ chắc: hỏi lại, đoán có báo, hay từ chối?
   - ③ **Ngoài phạm vi / thẩm quyền** — user đòi thứ không được phép làm, từ chối sao cho vẫn hữu ích?
   - ④ **Đặc thù domain** — sai cái gì thì user mất điểm, mất niềm tin, học sai kiến thức ngay?
3. Chỉ dùng data trong `data/` hoặc data giả tự sinh — không data thật của người thật ngoài pack đã rà. **Data được cấp thuộc quy định bảo mật** (xem README mục "Bảo mật dữ liệu được cung cấp") — không chia sẻ ra ngoài khoá, không commit vào repo nộp bài.

## 5 tiêu chí nghiệm thu bài toán *(áp cho MỌI hướng — kể cả tối ưu tính năng có sẵn)*

| # | Tiêu chí | Đạt khi |
|---|---|---|
| 1 | Pain cụ thể | Ai — đang làm gì — vướng đâu — hậu quả gì. "Mọi người thấy bất tiện" = không đạt |
| 2 | Bằng chứng | **(A)** khảo sát ≥20 người ngoài nhóm, ≥50% xác nhận, log toàn bộ câu hỏi + từng câu trả lời; và/hoặc **(B)** mining data: số đếm được + ≥5 ví dụ nguyên văn + phương pháp đếm kiểm lại được |
| 3 | Problem statement + impact | Không chữ AI; bảng impact ≥3 ứng viên (bao nhiêu người × tần suất × tốn gì mỗi lần) + lý do chọn + ứng viên đã loại |
| 4 | Lát cắt prototype được | Một câu theo đúng format trên, demo được trong 5 phút, build được trong thời gian sự kiện |
| 5 | User sẵn sàng thử | ≥3 người thật ngoài nhóm (tên cụ thể) đồng ý thử prototype trước demo |

*Canvas nháp nộp tại CP1; evidence và spec hoàn thiện dần, chốt tại spec.md 23:59 N1.*
