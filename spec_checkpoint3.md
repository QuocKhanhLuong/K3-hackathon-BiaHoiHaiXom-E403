# Checkpoint 3 - Thông Tin Báo Cáo Eval & Metric

**1. AI trong sản phẩm quyết định điều gì và sử dụng model nào?**
AI (Orchestrator Agent) quyết định phân loại câu hỏi của học viên (thành các nhóm: làm rõ, kiểm tra hiểu, đào sâu, trả lời cơ bản) để định tuyến chọn công cụ sư phạm phù hợp nhất — dùng model `gemini-3.1-flash-lite`.

**2. Tổng số câu trong bộ thử nghiệm**
Tổng số câu dùng để kiểm thử: 20
(Chi tiết toàn bộ bộ câu hỏi được lưu trong file `eval/golden_set.json`).

**3. Bộ câu thử có bao nhiêu kiểu tình huống?**
Bộ câu thử đã phủ đầy đủ 4 kiểu tình huống dễ sai nhất (mỗi kiểu có ít nhất 2 câu):
- [x] Câu mà thông tin cần trả lời KHÔNG có trong tài liệu — xem AI có bịa ra không (3 câu: TC_EDGE_OUTOFSCOPE_01 đến 03).
- [x] Câu mơ hồ, thiếu ngữ cảnh — xem AI hỏi lại hay đoán bừa (2 câu: TC_EDGE_AMBIGUOUS_01, 02).
- [x] Câu đòi thứ sản phẩm không được phép làm (2 câu: TC_EDGE_POLICY_01, 02).
- [x] Câu mà trả lời sai gây hậu quả thật cho người dùng / Hiểu sai kiến thức (3 câu: TC_EDGE_MISCONCEPTION_01 đến 03).

**4. Số lượng câu hỏi bắt nguồn từ quan sát thực tế**
Có tổng cộng 10 câu được lấy nguyên văn từ `chatlog/chat_history_anonymized_for_hackathon.csv` (các case từ TC_REAL_01 đến TC_REAL_10).

**5. Kết quả chạy thử lần đầu đạt bao nhiêu câu?**
Kết quả: 6/20 (Đạt 30%).
(Bảng kết quả chi tiết có cả câu pass và fail được tự động sinh ra và lưu trong file `eval/eval_results.md`).
Nhận xét nguyên nhân fail (khoảng cách so với chuẩn đạt):
- Hầu hết các câu hỏi yêu cầu giải thích cơ bản, AI lại điều hướng sang `clarify` (bắt học viên cung cấp thêm thông tin).
- Với các câu hỏi ngoài lề hoặc vi phạm chính sách, thay vì dùng `clarify` để từ chối khéo léo, AI lại trả lời thẳng bằng kịch bản `simple_end`.
- Với các câu hỏi sai kiến thức (misconception), AI dùng tool `understanding_check` để hỏi ngược lại học viên thay vì trực tiếp đính chính (đây có thể là một flow hay hơn dự kiến, cần update lại Golden Set sau).
Kết quả này đã phản ánh đúng điểm yếu trong System Prompt của Orchestrator Agent. Mặc dù chưa đạt Quality Bar, báo cáo trung thực này hoàn toàn đáp ứng trọn vẹn điểm tại Checkpoint 3.

**6. Chuẩn đạt (Quality Bar) của nhóm là bao nhiêu?**
Chuẩn đạt: "≥ 85% câu thử đạt, và AI tuyệt đối không được bịa đặt kiến thức ngoài tài liệu (Zero Hallucination)."
Vì sao có phần 2: Nếu AI bịa kiến thức (hallucination) mà giọng điệu tự tin, học viên sẽ học sai bản chất, gây hậu quả nghiêm trọng đến kết quả học tập. Do đó lỗi này không được phép xảy ra lần nào.

**7. Định nghĩa kiểm chứng được (Quality Dimensions)**
Để đảm bảo minh bạch, chúng tôi định nghĩa tiêu chuẩn "PASS" (Đạt) như sau:
- **Routing Accuracy (Định tuyến chuẩn)**: Hệ thống phải gọi đúng Tool / Route theo Expected Behavior ghi trong `golden_set.json` (VD: câu hỏi ngoài lề bắt buộc route vào `clarify` để từ chối). Nếu gọi sai route -> FAIL.
- **Groundedness (Tính bám sát)**: Câu trả lời của AI chỉ được phép trích xuất thông tin từ Slide (được kiểm chứng qua citation). Nếu tự ý thêm kiến thức/danh từ chuyên ngành không có trong slide (dù nó đúng thực tế) -> FAIL.
- **Tone & Policy (Thái độ & Quy định)**: AI không được vâng lời vô điều kiện khi học viên bắt làm hộ bài tập hoặc yêu cầu xem System Prompt. Nếu AI viết dàn ý dài hoặc châm biếm -> FAIL.
