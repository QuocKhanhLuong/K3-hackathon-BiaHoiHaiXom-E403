# Follow-up Suggestions Tool (`followup_suggestions`)

## 📌 1. Mục đích & Chức năng
Tool **Follow-up Suggestions Generator** tự động phân tích phản hồi vừa qua của Tutor và ngữ cảnh trang slide để sinh ra 2-3 câu hỏi gợi mở đào sâu dạng thẻ (Chips), giúp học viên bấm nhanh để tiếp tục tương tác.

---

## 📥 2. Parameters Đầu vào (Input Schema)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `tutor_answer` | `str` | Yes | Câu trả lời vừa qua của Tutor |
| `page_number` | `int` | No | Trang slide hiện tại (mặc định: `1`) |

### Example Request (JSON):
```json
{
  "tutor_answer": "Function Calling là kỹ thuật...",
  "page_number": 4
}
```

---

## 📤 3. Định dạng Kết quả Đầu ra (Output Schema)

| Field | Type | Description |
|---|---|---|
| `suggestions` | `List[str]` | Danh sách 2-3 câu hỏi gợi mở đào sâu |

### Example Response (JSON):
```json
{
  "suggestions": [
    "Ví dụ JSON Schema chuẩn khi định nghĩa 1 tool tra cứu tài liệu?",
    "Khi mô hình gọi sai tên Tool thì xử lý fallback ra sao?",
    "Cách test nghiệm thu Function Calling trong bài Hackathon?"
  ]
}
```

---

## 💻 4. Hướng dẫn Gọi trực tiếp bằng Python
```python
from backend.tools.followup_suggestions.tool import run_followup_suggestions_tool, FollowupInput

result = run_followup_suggestions_tool(FollowupInput(tutor_answer="...", page_number=4))
print(result.suggestions)
```
