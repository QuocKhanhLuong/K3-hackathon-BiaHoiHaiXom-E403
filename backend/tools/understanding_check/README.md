# Understanding Check Tool (`understanding_check`)

## 📌 1. Mục đích & Chức năng
Tool **Understanding Check (Quiz Generator)** có chức năng tự động khởi tạo bài kiểm tra mức độ hiểu bài của học viên đối với khái niệm vừa trao đổi. 

Hỗ trợ 2 định dạng bài kiểm tra:
1. `multiple_choice`: Bài Quiz trắc nghiệm 4 đáp án (A, B, C, D).
2. `short_answer`: Bài Quiz tự luận ngắn có **Khung ô gõ câu trả lời (Answer Input Box)** để học viên gõ tự do.

---

## 📥 2. Parameters Đầu vào (Input Schema)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `question` | `str` | Yes | Câu hỏi của học viên |
| `tutor_answer` | `str` | Yes | Câu trả lời vừa qua của Tutor |
| `page_number` | `int` | No | Trang slide hiện tại (mặc định: `1`) |

---

## 📤 3. Định dạng Kết quả Đầu ra (Output Schema)

| Field | Type | Description |
|---|---|---|
| `quiz_id` | `str` | Mã định danh duy nhất của bài Quiz |
| `quiz_type` | `str` | Định dạng bài kiểm tra (`"multiple_choice"` hoặc `"short_answer"`) |
| `concept` | `str` | Tên khái niệm được kiểm tra |
| `question` | `str` | Nội dung câu hỏi kiểm tra |
| `options` | `List[str]` | (Dành cho `multiple_choice`) Danh sách 4 lựa chọn đáp án |
| `correct_index` | `int` | (Dành cho `multiple_choice`) Chỉ số đáp án đúng (`0` đến `3`) |
| `expected_keywords` | `List[str]` | (Dành cho `short_answer`) Danh sách các từ khóa kỳ vọng trong câu trả lời |
| `explanation` | `str` | Lời giải thích khi trả lời đúng |

### Example Response for Short Answer (JSON):
```json
{
  "quiz_id": "q_1785386100",
  "quiz_type": "short_answer",
  "concept": "Vận dụng Khái niệm Cốt lõi",
  "question": "Theo bạn, tại sao Function Calling lại được gọi là 'Hợp đồng' (Contract)? (Gõ vào ô dưới):",
  "expected_keywords": ["schema", "hợp đồng", "cấu trúc", "json"],
  "explanation": "Chính xác! Function Calling cung cấp cấu trúc dữ liệu chuẩn hóa (JSON Schema)..."
}
```

---

## 💻 4. Hướng dẫn Gọi trực tiếp bằng Python
```python
from backend.tools.understanding_check.tool import run_understanding_check_tool, UnderstandingCheckInput

quiz = run_understanding_check_tool(UnderstandingCheckInput(question="giải thích Function Calling", tutor_answer="", page_number=4))
print(f"Quiz Type: {quiz.quiz_type}")
print(f"Question: {quiz.question}")
```
