# Learning Loop Orchestrator Master Agent (`orchestrator`)

## 📌 1. Mục đích & Chức năng
Tool **Learning Loop Orchestrator** là Agent quyết định trung tâm trong Workflow sơ đồ tư duy (**"Bước tiếp theo?"**). Agent phân tích câu hỏi của học viên và phản hồi của Tutor để điều hướng tự động sang 1 trong 4 nhánh sư phạm tiếp theo.

---

## 📥 2. Parameters Đầu vào (Input Schema)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `question` | `str` | Yes | Câu hỏi của học viên |
| `tutor_answer` | `str` | Yes | Câu trả lời có căn cứ vừa được Tutor tạo |
| `chat_history` | `List[dict]` | No | Lịch sử hội thoại vừa qua |

### Example Request (JSON):
```json
{
  "question": "Hãy giải thích về Function Calling",
  "tutor_answer": "Function Calling cung cấp hợp đồng rõ ràng dạng JSON Schema..."
}
```

---

## 📤 3. Định dạng Kết quả Đầu ra (Output Schema)

| Field | Type | Description |
|---|---|---|
| `branch` | `str` | Mã nhánh được chọn: `"simple_end"`, `"clarify"`, `"understanding_check"`, `"followup"` |
| `title` | `str` | Tên hiển thị của nút quyết định (vd: `"Cần kiểm tra hiểu"`) |
| `description` | `str` | Lý do rẽ nhánh của Master Agent |
| `next_node` | `str` | Tên Tool Agent tiếp theo sẽ được kích hoạt |

### Example Response (JSON):
```json
{
  "branch": "understanding_check",
  "title": "Cần kiểm tra hiểu",
  "description": "Khái niệm vừa trao đổi có độ phức tạp cao, kích hoạt Tool Understanding Check tạo Quiz trắc nghiệm.",
  "next_node": "Understanding Check"
}
```

---

## 💻 4. Hướng dẫn Gọi trực tiếp bằng Python
```python
from backend.tools.orchestrator.tool import run_orchestrator_tool, OrchestratorInput

input_data = OrchestratorInput(
    question="Function Calling là gì?",
    tutor_answer="Function Calling là kỹ thuật..."
)
decision = run_orchestrator_tool(input_data)
print(f"Decision Branch: {decision.branch}")
print(f"Next Node: {decision.next_node}")
```
