# Data pack — VLearn

## Có sẵn trong pack

- `chatlog/chat_history_anonymized_for_hackathon.csv` — **2.522 dòng hội thoại thật** học viên × AI tutor, đã ẩn danh toàn bộ ID (user/conversation/turn/message → mã U/C/T/M) và đã quét sạch thông tin nhạy cảm.
- `chatlog/DATA_DICTIONARY.md` — mô tả từng field của file trên (đọc trước khi mining).
- `transcript/` — **6 transcript bài giảng bản sạch** (~700 đoạn có mã trích dẫn `[Txx-NNN]`): Day 1 Foundation, Day 2 xác định bài toán (3 file), và 2 buổi theo chủ đề. Đã sửa lỗi nhận dạng giọng nói, ẩn danh tên học viên, rút gọn phần hoạt động lớp — xem `transcript/README.md`.
- `slides/` — **2 bộ slide bài giảng bản hackathon** (Day 1 AI & LLM Foundation · Day 2 Xác định bài toán cho AI, 29 trang/bộ, có watermark): bản rút gọn từ slide gốc, một số trang giữ nguyên footer số trang gốc để đối chiếu trích dẫn.

## Luật dùng & bảo mật

- Dùng để mining evidence, dựng golden set, và làm context cho prototype — **chỉ trong phạm vi hackathon**.
- Không chia sẻ ra ngoài khoá học: không đăng mạng xã hội, không gửi người ngoài, không đưa vào dataset/repo công khai.
- Không đổ nguyên file lên repo nộp bài của nhóm — trích ngắn để minh hoạ; golden set ghi mã đoạn/mã hội thoại thay vì dán nguyên văn dài.
- Đưa vào công cụ AI ngoài: chỉ phần tối thiểu cần thiết; lưu ý free tier có thể dùng dữ liệu để huấn luyện.
- Không cố suy ngược danh tính từ mã ẩn danh.
- Sau sự kiện, xoá bản sao data khỏi máy và công cụ đã upload nếu ban tổ chức yêu cầu.

Chi tiết quy định: README gốc của repo, mục "Bảo mật dữ liệu được cung cấp".
