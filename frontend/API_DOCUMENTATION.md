# VLearn Frontend API — Phase 0 + 1

Tài liệu này mô tả contract hiện tại giữa frontend và FastAPI backend sử dụng
`ai_core`. Gemini/BYOK và việc gửi đáp án đúng từ client không còn được hỗ trợ.

## Chạy local

Từ thư mục gốc:

```powershell
python -m pip install -r backend/requirements-dev.txt
python -m pip install -e ai_core
Copy-Item .env.example .env
# Điền OPENAI_API_KEY trong .env
python -m uvicorn backend.main:app --port 8000
```

Mở `http://localhost:8000`.

## Nguyên tắc contract

- Backend tạo và sở hữu `conversation_id`, `turn_id`, `action_id`.
- Browser được định danh bằng anonymous signed HttpOnly cookie.
- OpenAI API key chỉ tồn tại ở server, không gửi trong request.
- Client chỉ nhận option ID/text; không nhận đáp án đúng hoặc expected answer.
- `tool_trace`, raw model output, prompt name và exception không thuộc public API.
- Request/response có `X-Request-ID` để đối chiếu log.

## API v1

### `GET /api/v1/health/live`

Kiểm tra process còn sống.

### `GET /api/v1/health/ready`

Kiểm tra `ai_core` và slide repository.

### `POST /api/v1/conversations`

Request:

```json
{
  "course_id": "default"
}
```

Response:

```json
{
  "conversation_id": "conv_...",
  "status": "active",
  "course_id": "default"
}
```

### `POST /api/v1/conversations/{conversation_id}/turns`

Request:

```json
{
  "question": "Key và Value khác nhau như thế nào?",
  "selected_text": "Key dùng để so khớp với Query...",
  "page_number": 4,
  "conversation_history": [],
  "idempotency_key": "optional-client-request-id"
}
```

Response khi chờ micro-check:

```json
{
  "request_id": "req_...",
  "conversation_id": "conv_...",
  "turn_id": "turn_...",
  "status": "awaiting_response",
  "message": {
    "role": "assistant",
    "content": "..."
  },
  "route": {
    "name": "check",
    "confidence": 0.91
  },
  "action": {
    "type": "multiple_choice",
    "action_id": "action_...",
    "question": "Phương án nào mô tả đúng vai trò của Key?",
    "options": [
      {"id": "opt_a", "text": "..."},
      {"id": "opt_b", "text": "..."}
    ],
    "suggested_inputs": [],
    "target_concept": "Key"
  },
  "citations": [
    {
      "citation_id": "ctx_1",
      "snippet": "...",
      "source_location": "trang 4",
      "page_number": 4
    }
  ],
  "suggestions": []
}
```

### `POST /api/v1/turns/{turn_id}/responses`

Resume clarification hoặc check đang chờ:

```json
{
  "action_id": "action_...",
  "value": "opt_b",
  "idempotency_key": "submit-uuid"
}
```

`idempotency_key` bắt buộc. Gửi lại cùng key và cùng payload trả lại kết quả cũ;
dùng lại key với payload khác trả `409`.

### `GET /api/v1/conversations/{conversation_id}`

Khôi phục messages, turns và pending action của session hiện tại. Conversation
thuộc session khác được trả như không tồn tại.

## Compatibility API cho frontend hiện tại

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/slides` | Danh sách slide |
| `GET` | `/api/slides/{page}/render` | Render PNG |
| `POST` | `/api/tutor/ask` | Hỏi không streaming |
| `POST` | `/api/tutor/ask/stream` | Hỏi bằng SSE |
| `POST` | `/api/clarification/submit` | Resume clarification |
| `POST` | `/api/quiz/submit` | Nộp quiz bằng server-side action |

### `POST /api/tutor/ask/stream`

Request:

```json
{
  "question": "Key là gì?",
  "selected_text": "",
  "page_number": 1,
  "chat_history": [],
  "thread_id": "conv_..."
}
```

`thread_id` ở compatibility API chính là server-generated conversation ID.
Lần đầu có thể để `null`; frontend phải lưu ID từ response và gửi lại để resume
clarification.

SSE sử dụng envelope tương thích frontend:

```text
data: {"type":"trace","request_id":"req_...","tool":"learning_loop","status":"running",...}

data: {"type":"result","request_id":"req_...","data":{...}}
```

Lỗi:

```text
data: {"type":"error","request_id":"req_...","error":{"code":"AI_SERVICE_UNAVAILABLE","message":"..."}}
```

Progress chỉ là stage an toàn do backend xác nhận, không phải chain-of-thought
hoặc raw tool trace.

### Tool data clarification

```json
{
  "type": "clarification_request",
  "action_id": "action_...",
  "thread_id": "conv_...",
  "clarifying_question": "Bạn muốn làm rõ khía cạnh nào?",
  "suggested_inputs": [
    "Mình muốn hiểu định nghĩa và ý chính.",
    "Mình muốn xem một ví dụ cụ thể.",
    "Mình muốn biết cách áp dụng vào bài học."
  ]
}
```

### Tool data quiz

```json
{
  "type": "multiple_choice",
  "quiz_id": "action_...",
  "thread_id": "conv_...",
  "quiz_type": "multiple_choice",
  "concept": "Key",
  "question": "...",
  "options": ["...", "...", "..."]
}
```

Không có `correct_index`, `correct_option`, `expected_answer`,
`expected_keywords` hoặc `explanation` trước khi nộp bài.

### `POST /api/quiz/submit`

Trắc nghiệm:

```json
{
  "quiz_id": "action_...",
  "thread_id": "conv_...",
  "quiz_type": "multiple_choice",
  "selected_option": 1,
  "question_text": "...",
  "page_number": 4
}
```

Tự luận:

```json
{
  "quiz_id": "action_...",
  "thread_id": "conv_...",
  "quiz_type": "short_answer",
  "user_text_answer": "...",
  "question_text": "...",
  "page_number": 4
}
```

Backend lấy đáp án/checkpoint từ `quiz_id`, không tin dữ liệu chấm điểm do client
cung cấp.

## Error JSON

Endpoint không streaming trả lỗi:

```json
{
  "request_id": "req_...",
  "error": {
    "code": "STATE_CONFLICT",
    "message": "Trạng thái hiện tại không cho phép thao tác này."
  }
}
```

Các code chính:

- `RESOURCE_NOT_FOUND`
- `STATE_CONFLICT`
- `INVALID_ACTION`
- `AI_SERVICE_UNAVAILABLE`
- `INTERNAL_ERROR`

## Giới hạn Phase 1

Conversation repository và LangGraph checkpoint vẫn nằm trong RAM. Refresh
browser có thể restore trong cùng process, nhưng restart server hoặc chạy nhiều
worker sẽ mất/không chia sẻ state. PostgreSQL và durable checkpointer thuộc
Phase 2.
