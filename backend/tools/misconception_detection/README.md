# Misconception Detection Tool (`misconception_detection`)

## 📌 1. Mục đích & Chức năng
Tool **Misconception Detection (Phát hiện điểm nhầm lẫn)** được tự động kích hoạt khi học viên chọn sai đáp án trong bài Quiz. Tool phân tích nguyên nhân nhầm lẫn, giải thích lại trúng điểm sai, đưa ra ví dụ minh họa mới và tạo 1 bài Quiz phụ để kiểm tra lại ngay lập tức.

---

## 📥 2. Parameters Đầu vào (Input Schema)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `question_text` | `str` | Yes | Nội dung câu hỏi Quiz mà học viên vừa làm sai |
| `selected_option` | `int` | Yes | Chỉ số lựa chọn sai của học viên (`0` đến `3`) |
| `correct_option` | `int` | Yes | Chỉ số đáp án đúng thực tế |
| `page_number` | `int` | No | Trang slide hiện tại (mặc định: `1`) |

### Example Request (JSON):
```json
{
  "question_text": "Điểm khác biệt giữa Context Window và Weights là gì?",
  "selected_option": 0,
  "correct_option": 1,
  "page_number": 5
}
```

---

## 📤 3. Định dạng Kết quả Đầu ra (Output Schema)

| Field | Type | Description |
|---|---|---|
| `misconception_point` | `str` | Điểm hiểu sai cốt lõi được trích xuất |
| `re_explanation` | `str` | Đoạn giải thích sửa lỗi tư duy cho học viên |
| `new_example` | `str` | Ví dụ minh họa mới trực quan |
| `recheck_question` | `Object` | Bài Quiz phụ mới để kiểm tra lại hiểu bài |

### Example Response (JSON):
```json
{
  "misconception_point": "Học viên đang nhầm lẫn giữa dữ liệu trong Context Window...",
  "re_explanation": "💡 Điểm cần lưu ý: Context Window chỉ chứa dữ liệu nạp tạm thời...",
  "new_example": "📌 Ví dụ mới: Giống như khi bạn đi thi được mang tài liệu vào...",
  "recheck_question": {
    "quiz_id": "rq_1785386000",
    "question": "Nếu slide được cập nhật trang mới trong buổi học...",
    "options": ["Huấn luyện lại", "Nạp trang slide mới vào Context Window", ...],
    "correct_index": 1
  }
}
```

---

## 💻 4. Hướng dẫn Gọi trực tiếp bằng Python
```python
from backend.tools.misconception_detection.tool import run_misconception_detection_tool, MisconceptionInput

result = run_misconception_detection_tool(MisconceptionInput(
    question_text="Context vs Weights",
    selected_option=0,
    correct_option=1
))
print(result.misconception_point)
print(result.re_explanation)
print(result.recheck_question.question)
```
