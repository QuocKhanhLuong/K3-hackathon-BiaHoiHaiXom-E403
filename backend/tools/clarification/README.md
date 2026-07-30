# Clarification Tool (`clarification`)

## 📌 1. Mục đích & Chức năng
Tool **Hỏi làm rõ (Clarification Tool)** được kích hoạt khi Master Agent phát hiện câu hỏi của học viên bị thiếu thông tin hoặc chưa rõ ngữ cảnh. Tool sẽ đưa ra câu hỏi định hướng kèm danh sách các lựa chọn gợi ý cho học viên bấm phản hồi nhanh.

---

## 📥 2. Parameters Đầu vào (Input Schema)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `question` | `str` | Yes | Câu hỏi mơ hồ hoặc quá ngắn của học viên |
| `page_number` | `int` | No | Trang slide hiện tại (mặc định: `1`) |

### Example Request (JSON):
```json
{
  "question": "là sao",
  "page_number": 4
}
```

---

## 📤 3. Định dạng Kết quả Đầu ra (Output Schema)

| Field | Type | Description |
|---|---|---|
| `clarifying_question` | `str` | Câu hỏi gợi mở để làm rõ yêu cầu |
| `suggested_inputs` | `List[str]` | Danh sách 3 phương án gợi ý cho học viên bấm nhanh |

### Example Response (JSON):
```json
{
  "clarifying_question": "Bạn muốn mình làm rõ hơn về khái niệm chung hay hướng dẫn áp dụng...",
  "suggested_inputs": [
    "Giải thích theo ví dụ dự án thực tế",
    "So sánh với cách làm thông thường",
    "Hướng dẫn chi tiết các bước triển khai"
  ]
}
```

---

## 💻 4. Hướng dẫn Gọi trực tiếp bằng Python
```python
from backend.tools.clarification.tool import run_clarification_tool, ClarificationInput

result = run_clarification_tool(ClarificationInput(question="chưa rõ", page_number=4))
print(result.clarifying_question)
print(result.suggested_inputs)
```
