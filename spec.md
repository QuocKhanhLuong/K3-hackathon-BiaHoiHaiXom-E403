# AI SPEC — Learning Loop Orchestrator · Nhóm BiaHoiHaiXom · Zone 1
Hướng: [x] B — Trợ lý Học viên  [ ] A — VLearn  [ ] C — Làn mở
Loại: [x] Tối ưu tính năng có sẵn  [ ] Tính năng mới

- AI trong sản phẩm: Orchestrator Agent quyết định route câu hỏi của học viên sang các hành vi sư phạm phù hợp (clarify / check / deep / simple) để định tuyến tiếp theo, dùng model gemini-3.1-flash-lite.

## §1. User & Job
- Job executor + workflow: học viên đang đọc tài liệu trong buổi học, vừa nhận được câu trả lời từ tutor, muốn biết mình đã hiểu đúng hay chưa và nên học tiếp gì tiếp theo.
- Core JTBD: hiểu đúng một khái niệm trong tài liệu để có thể tiếp tục học phần tiếp theo.
- Problem statement: học viên thường nhận được một lời giải thích nhưng chưa có đủ hỗ trợ để biết mình đã hiểu đúng, còn vướng ở đâu hoặc nên tìm hiểu tiếp điều gì.
- Evidence (đạt chuẩn B — mining):
  - Số liệu mining: 1.261 lượt hỏi–đáp, 369 học viên, 585 hội thoại, 276 hội thoại multi-turn (47.2%).
  - Tutor pedagogical move: review_concept chiếm 1.074/1.261 lượt (85.17%).
  - Learning loop signal: asked_check_question=True chỉ 3/1.261 lượt (0.24%); misconception và follow-up đều bằng 0.
  - Grounding: 582/1.261 câu trả lời không có citation (46.15%).
  - ≥5 quote/ví dụ nguyên văn + nguồn:
    - “review_concept chiếm 85.17%” — [eda_output/EDA_REPORT.md](eda_output/EDA_REPORT.md)
    - “asked_check_question=True chỉ 3 lượt” — [eda_output/EDA_REPORT.md](eda_output/EDA_REPORT.md)
    - “Non-empty misconception = 0” — [eda_output/EDA_REPORT.md](eda_output/EDA_REPORT.md)
    - “Non-empty follow-up = 0” — [eda_output/EDA_REPORT.md](eda_output/EDA_REPORT.md)
    - “T0317: Hiện tại cách thức tiếp cận nghiên cứu AI bao gồm...” — [eda_output/evidence_examples.csv](eda_output/evidence_examples.csv)
    - “T0466: giải thích chi tiết hơn slide 26” — [eda_output/evidence_examples.csv](eda_output/evidence_examples.csv)
  - Log đầy đủ: [eda_output/EDA_REPORT.md](eda_output/EDA_REPORT.md), [eda_output/evidence_examples.csv](eda_output/evidence_examples.csv), [data/vlearn-pack/chatlog/chat_history_anonymized_for_hackathon.csv](data/vlearn-pack/chatlog/chat_history_anonymized_for_hackathon.csv)

## §2. Impact & quyết định chọn
- Bảng impact ≥3 ứng viên:

| Ứng viên | Người gặp | Tần suất | Mỗi lần tốn gì | Khả thi trong hackathon | Kết quả |
|---|---:|---:|---|---|---|
| Learning Loop Orchestrator | 350/369 users (94.8%) | cao | học viên mất thêm 30–60 giây để xác nhận hiểu bài và chọn bước học tiếp | Cao | Chọn |
| Citation-first explanation assistant | 255/369 users (69.1%) | trung bình | học viên cần tin cậy hơn vào nguồn, nhưng đây là constraint thay vì pain chính | Cao | Loại |

- Ứng viên đã loại + lý do:
  - Citation-first explanation assistant: pain có thật, nhưng nó là điều kiện tin cậy chứ không phải trung tâm của vấn đề; nếu chỉ làm citation mà không giúp học viên kiểm tra hiểu bài thì vòng học vẫn không đóng.
- Ứng viên chọn + lý do bằng số:
  - Learning Loop Orchestrator phù hợp vì nó chạm đúng khoảng trống: 85.17% lượt dùng một move sư phạm duy nhất, còn các tín hiệu như check question, misconception và follow-up gần như bằng 0; đây là khoảng trống rõ và có thể demo bằng một decision layer rõ ràng.

## §3. Giải pháp tương tự đã nghiên cứu
- Khanmigo / Study Mode: đáng học ở chỗ họ đưa follow-up question và adaptive learning; đáng né ở chỗ flow thường gắn quá nhiều vào experience toàn diện, khiến slice này trở nên quá rộng.
- NotebookLM: đáng học ở chỗ luôn làm rõ nguồn và citation; đáng né ở chỗ nó chủ yếu hỗ trợ tìm hiểu và tóm tắt, chưa tập trung vào “sau câu trả lời, nên làm gì tiếp theo để kiểm tra hiểu bài”.
- Duolingo / Quizlet AI: đáng học ở chỗ họ làm micro-check và luyện tập ngắn; đáng né ở chỗ mục tiêu của họ là luyện tập, không phải điều hướng một lượt học tập trong tài liệu có context cụ thể.
- Điểm khác của nhóm: tập trung vào một quyết định sư phạm duy nhất sau câu trả lời hiện tại: check understanding, ask clarification, suggest follow-up hay end turn.

## §4. Thiết kế
- Lát cắt một câu: với một học viên vừa nhận lời giải thích về một khái niệm trong tài liệu, hệ thống quyết định bước tiếp theo phù hợp để xác nhận hiểu đúng, làm rõ thiếu thông tin hoặc đào sâu nội dung.
- Non-goals (không build):
  - Không xây toàn bộ tutor generative experience mới.
  - Không tự động chấm điểm bài tập dài hay tạo curriculum toàn diện.
  - Không thay thế vai trò giảng viên/TA trong các câu hỏi phức tạp.
  - Không build hệ thống recommendation dài hạn dựa trên lịch sử học tập toàn bộ khóa.
- Mức prototype nhắm tới: [x] Mock — theo kết quả chạy thử, core decision logic và flow trải nghiệm có thể chạy thật bằng AI; phần UI và data có thể mock/giả.
- Automation: [x] conditional — AI chỉ tự làm khi có căn cứ trong tài liệu và tình huống đủ rõ; nếu không chắc, hệ thống chuyển sang hỏi lại hoặc dừng lại.
- §4b. Nguyên tắc đã áp dụng:

| Nguyên tắc | Áp cụ thể vào đâu trong prototype |
|---|---|
| G10 — Thu hẹp phạm vi khi nghi ngờ | Nếu câu hỏi thiếu thông tin hoặc ngoài tài liệu, hệ thống hỏi lại hoặc từ chối khéo léo thay vì đoán.
| G2 — Làm rõ nó làm tốt đến đâu | Output sẽ kèm câu “dựa trên tài liệu hiện tại” và giới hạn phạm vi.
| G9 — Sửa dễ dàng | User có thể sửa câu hỏi hoặc chọn bỏ qua step tiếp theo ngay trong flow.
| G11 — Giải thích vì sao | Mỗi hành động tiếp theo sẽ có lý do ngắn gọn, ví dụ “vì câu hỏi hiện tại cần kiểm tra hiểu bài”. |
| PAIR — Explainability + Trust | Mỗi đề xuất follow-up hoặc check understanding đều dựa trên câu hỏi và nội dung tài liệu vừa được trả lời. |
| PAIR — Errors + Graceful Failure | Nếu không có căn cứ, hệ thống không bịa thêm kiến thức mà chuyển sang clarification hoặc end-turn. |

## §5. Kiểu lỗi — 4 lớp chỗ khó + kịch bản

| Lớp | Kịch bản cụ thể | Hành vi mong muốn | Nguyên tắc áp dụng |
|---|---|---|---|
| 1. Nguồn sự thật | AI bịa kiến thức khi câu hỏi nằm ngoài slide hoặc không có citation | Từ chối khéo léo, nói rõ không có căn cứ trong tài liệu | G10, PAIR Explainability |
| 1. Nguồn sự thật | AI dùng kiến thức bên ngoài để “giải thích” một khái niệm chưa có trong slide | Chỉ dùng thông tin có trong tài liệu, nếu không có thì nói rõ | G10, G2 |
| 2. Mơ hồ / thiếu thông tin | Học viên hỏi “giải thích đoạn này” nhưng không nói rõ đoạn nào | Hỏi lại một câu ngắn để lấy ngữ cảnh | G10, G9 |
| 2. Mơ hồ / thiếu thông tin | Học viên viết câu hỏi ngắn, thiếu mục tiêu học tập | Chuyển sang clarification hoặc đề xuất một câu hỏi rõ hơn | G10 |
| 3. Ngoài phạm vi / thẩm quyền | Học viên yêu cầu “giúp làm bài tập/đáp án hộ” | Từ chối lịch sự, giữ phạm vi hỗ trợ học tập | G10, PAIR Trust |
| 3. Ngoài phạm vi / thẩm quyền | Học viên yêu cầu xem system prompt hoặc “bạn là AI gì?” | Trả lời giới hạn, không tiết lộ cấu trúc hệ thống | G10 |
| 4. Đặc thù domain | Học viên có hiểu nhầm và cần được sửa đúng ngay | Phát hiện misconception, giải thích lại đúng phần nhầm và cho ví dụ mới | G11, PAIR Errors |
| 4. Đặc thù domain | Học viên hỏi về khái niệm chuyên sâu nhưng cấp độ hiện tại chưa đủ | Đề xuất follow-up phù hợp hoặc kết thúc lượt thay vì “đi quá sâu” | G2, G11 |

## §6. Bốn đường đi của trải nghiệm
- Happy path: học viên nhận câu trả lời và hệ thống đề xuất một micro-check hoặc follow-up phù hợp, giúp học viên tự kiểm tra hiểu bài.
- Low-confidence (②): nếu model không chắc, hệ thống hỏi lại một câu ngắn thay vì tự đoán.
- Failure / không căn cứ (①): nếu không tìm thấy căn cứ trong tài liệu, hệ thống nói rõ và dừng lại hoặc chuyển sang clarification.
- Correction (user sửa): nếu học viên phản hồi lại câu hỏi hoặc sửa câu hỏi, hệ thống cập nhật hướng điều phối và chạy lại flow mới.
- Khi bị đòi ngoài phạm vi (③): hệ thống giữ giới hạn sư phạm, không làm hộ bài tập hoặc bịa kiến thức.
- Case đặc thù domain (④): nếu học viên có misconception, hệ thống sẽ giải thích lại đúng phần sai và cho ví dụ kiểm tra mới.

## §7. Kiểm thử
- Chiều chất lượng + định nghĩa kiểm chứng được:
  - Routing accuracy: route đúng theo expected behavior (clarify / check / deep / simple).
  - Groundedness: mỗi câu trả lời phải có căn cứ từ tài liệu; nếu bịa kiến thức thì fail.
  - Tone & policy: tránh trả lời vượt phạm vi, không làm hộ bài tập, không tiết lộ system prompt.
- Golden set: tổng cộng 32 case, gồm 12 case lấy từ chatlog thật, 5 out-of-scope, 4 ambiguous, 7 policy violation và 4 misconception; bộ này phủ đủ 4 lớp chỗ khó và có ít nhất 2 case mỗi lớp.
- Quality bar (chốt từ 23:59 và giữ nguyên):
  - Đạt khi đạt ít nhất 85% case trong golden set.
  - AI tuyệt đối không được bịa kiến thức ngoài tài liệu: 0 hallucination.
  - Routing accuracy tối thiểu 90%.
- Kết quả các lượt chạy: lần đầu chạy thử có 15/32 case đạt (46.9%) — xem [eval/eval_results.md](eval/eval_results.md). Các lỗi nổi bật gồm:
  - nhiều câu đơn giản bị route sai sang check thay vì simple;
  - các case cần clarification bị route sai sang deep hoặc unknown;
  - các case về policy/jailbreak chưa được xử lý ổn định;
  - misconception cases chưa luôn được đính chính trực tiếp đúng cách.

## §8. Phân công & kế hoạch
- Giai đoạn tiếp theo: ưu tiên sửa prompt để giảm lỗi route trong các case clarify, policy, misconception trước khi chạy lại toàn bộ golden set.

## §9. Changelog
| Thời điểm | Đổi gì | Vì sao |
|---|---|---|
| CP1 | Chọn Learning Loop Orchestrator làm pain chính | Vì dữ liệu cho thấy thiếu check understanding và follow-up, trong khi review_concept chiếm phần lớn phản hồi |
| CP3 | Dựng flow conditional với clarification / check / deep / end-turn | Để tránh bịa kiến thức và giữ phạm vi rõ |
| CP5 | Cập nhật quality bar và case edge | Vì vòng test đầu cho thấy model dễ sai trong case ngoài phạm vi và ambiguous |
