# CP1 Canvas Draft — VLearn

## 1. Hướng

**Hướng A — Tối ưu tutor hiện có trên VLearn.**

## 2. Job executor

Học viên đang tự học một bài trên VLearn và bị mắc ở một khái niệm cụ thể trong tài liệu.

## 3. Job to be Done

Hiểu đúng khái niệm đang học để có thể tiếp tục phần tiếp theo, đồng thời biết mình
đã hiểu đúng hay vẫn còn nhầm ở điểm nào.

## 4. Evidence ban đầu từ data

Dataset có **1,261** lượt hỏi-đáp, **369** user và
**585** conversation.

- `review_concept` chiếm **85.17%** số lượt.
- Chỉ **155** lượt (12.29%)
  có dấu hiệu hỏi kiểm tra hiểu bài theo field hoặc heuristic.
- Misconception non-empty: **0** lượt.
- Follow-up non-empty: **0** lượt.
- **46.15%** output không có citation.

> Lưu ý: cần bổ sung 5 ví dụ nguyên văn đã manual-review và khảo sát user để xác nhận hậu quả.

## 5. Painpoint draft

Học viên thường nhận được lời giải thích nhưng không có đủ tín hiệu để biết mình đã
hiểu đúng hay chưa. Khi học viên tiếp tục gặp khó khăn, tutor có thể chưa đổi cách hỗ
trợ theo điểm mắc thực tế, khiến hiểu lầm không được phát hiện và việc học bị kéo dài.

## 6. Problem statement — không chứa AI/solution

Học viên đang tự học từ tài liệu thường không biết liệu mình đã hiểu đúng một khái
niệm sau khi được giải thích hay chưa. Những điểm hiểu sai không được nhận diện,
khiến các lượt hỗ trợ tiếp theo thiếu căn cứ để điều chỉnh theo khó khăn thực tế của
từng người.

## 7. Impact table

| Ứng viên | Turn bị ảnh hưởng | User bị ảnh hưởng | Conversation bị ảnh hưởng | Quyết định |
|---|---|---|---|---|
| Tutor trả lời nhưng chưa đóng vòng kiểm tra hiểu bài | 87.7% | 94.8% | 93.0% | Chọn/validate sâu |
| Hành vi sư phạm tập trung quá mạnh vào giải thích lại | 85.2% | 88.3% | 89.6% | Constraint hoặc loại khỏi scope |
| Tutor tiếp tục dùng review_concept ở các lượt liên tiếp | 41.7% | 46.1% | 39.0% | Chọn/validate sâu |
| Câu trả lời không có citation để học viên kiểm chứng | 46.1% | 69.1% | 58.0% | Constraint hoặc loại khỏi scope |
| Một nhóm lượt phản hồi có latency cao | 10.1% | 22.2% | 15.9% | Constraint hoặc loại khỏi scope |

## 8. Lát cắt prototype

Với một học viên đang hỏi về một khái niệm trong tài liệu, hệ thống quyết định nước
đi sư phạm tiếp theo dựa trên nguồn học và tín hiệu hiểu bài hiện có, để tạo một phản
hồi giúp phát hiện hoặc xử lý điểm học viên chưa hiểu.

## 9. Automation dự kiến

**Conditional automation.** Hệ thống tự thực hiện khi có đủ nguồn và context; khi
thiếu căn cứ hoặc input mơ hồ, hệ thống hỏi làm rõ hoặc nói rõ giới hạn.

## 10. User sẵn sàng thử

- [Tên 1]
- [Tên 2]
- [Tên 3]

## 11. Phân công

- Quốc Khánh: data mining, problem framing, policy/agent logic.
- [Thành viên 2]: manual annotation và user research.
- [Thành viên 3]: frontend prototype.
- [Thành viên 4]: evaluation, validation và documentation.
