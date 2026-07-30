# Grounded Answer Generator Tool (`grounded_answer`)

## 📌 1. Mục đích & Chức năng
Tool **Grounded Answer Generator** nhận câu hỏi của học viên và đoạn văn bản được chọn trên slide bài giảng, tra cứu vector embedding/kiến thức bài giảng và trả về câu trả lời có trích dẫn mã trang slide `[trang N]`.

---

## 📥 2. Parameters Đầu vào (Input Schema)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `question` | `str` | Yes | Câu hỏi hoặc yêu cầu của học viên |
| `selected_text` | `str` | No | Đoạn văn bản học viên bôi đen trên slide (mặc định: `""`) |
| `page_number` | `int` | No | Số trang slide học viên đang xem (mặc định: `1`) |

### Example Request (JSON):
```json
{
  "question": "Hãy giải thích về Function Calling",
  "selected_text": "Function Calling & Agent Tools Contract",
  "page_number": 4
}
```

---

## 📤 3. Định dạng Kết quả Đầu ra (Output Schema)

| Field | Type | Description |
|---|---|---|
| `answer` | `str` | Câu trả lời của Tutor kèm mã trích dẫn `[trang N]` |
| `citations` | `List[int]` | Danh sách các số trang slide được trích dẫn |
| `page_number` | `int` | Trang slide xử lý |

### Example Response (JSON):
```json
{
  "answer": "Theo trang 4, Function Calling ra đời cung cấp một \"Hợp đồng\" rõ ràng dạng JSON Schema cho Agent...",
  "citations": [4],
  "page_number": 4
}
```

---

## 💻 4. Hướng dẫn Gọi trực tiếp bằng Python
```python
from backend.tools.grounded_answer.tool import run_grounded_answer_tool, GroundedAnswerInput

input_data = GroundedAnswerInput(
    question="Function Calling là gì?",
    page_number=4
)
result = run_grounded_answer_tool(input_data)
print(result.answer)
print(result.citations)
```
