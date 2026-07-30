# 📚 VLearn Frontend API Integration Specification & Documentation

Tài liệu hướng dẫn kết nối **Frontend UI VLearn** với bất kỳ hệ thống **Backend REST API** bên ngoài (Node.js, Python, Java, Go, C#, v.v.).

---

## 🌐 1. Base URL & CORS Settings

- **Default Base URL:** `http://localhost:8000` (hoặc domain backend của bạn)
- **Header:** `Content-Type: application/json`
- **CORS Requirement:** Backend cần bật CORS (`Access-Control-Allow-Origin: *` hoặc origin của Frontend).

---

## 📌 2. Danh sách Các Endpoints Cần Hỗ Trợ

Frontend UI tương tác với Backend qua 3 endpoints chính:

| HTTP Method | Endpoint Path | Chức năng chính |
|---|---|---|
| `GET` | `/api/slides` | Lấy danh sách toàn bộ các trang Slide bài giảng |
| `POST` | `/api/tutor/ask` | Gửi câu hỏi học viên ➔ Nhận câu trả lời + Quyết định Orchestrator + Tool Card + 3 Gợi ý |
| `POST` | `/api/quiz/submit` | Nộp bài Quiz (Trắc nghiệm hoặc Tự luận ngắn) ➔ Nhận kết quả & Misconception Alert |

---

## 📑 3. Chi tiết API Specs

### 3.1. `GET /api/slides`
Lấy dữ liệu toàn bộ các trang Slide hiển thị ở cột bên trái.

#### 📥 Query Parameters:
*(Không có)*

#### 📤 Successful Response (`200 OK`):
```json
{
  "total_pages": 5,
  "slides": [
    {
      "page": 1,
      "title": "AI Product Thinking & Requirements",
      "subtitle": "AICB-P1 · Ngày 5 · Build agent xong, nhưng sản phẩm cho ai?",
      "content": "<p><b>Tên Giảng Viên:</b> VinUniversity Phase 1 Tuần 1 2026.</p><p>Giới thiệu tổng quan về tư duy thiết kế sản phẩm AI cho người dùng thật.</p>",
      "code": "Lecture_material_ms204v3b_r9mo78"
    },
    {
      "page": 2,
      "title": "HÃY SUY NGHĨ: Bạn đã build xong Agent chưa?",
      "subtitle": "Vấn đề của người dùng vs Prototype kỹ thuật",
      "content": "<p>Nhiều đội nhóm tập trung 90% thời gian gọi API và chỉnh prompt...</p>",
      "code": "Lecture_material_ms204v3b_r9mo78"
    }
  ]
}
```

---

### 3.2. `POST /api/tutor/ask`
Endpoint chính xử lý khi học viên nhập câu hỏi hoặc bôi đen văn bản trên slide.

#### 📥 Request Body Schema (JSON):
```json
{
  "question": "Function Calling là gì",
  "selected_text": "Text-based ReAct vs Structured Function Calling",
  "page_number": 4,
  "chat_history": [],
  "api_key": "AIzaSy..." // Optional (Nếu người dùng bật BYOK)
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | `string` | **Yes** | Câu hỏi của học viên |
| `selected_text` | `string` | No | Đoạn văn bản bôi đen trên Slide (nếu có) |
| `page_number` | `integer` | No | Số trang Slide hiện tại (Mặc định: `1`) |
| `chat_history` | `array` | No | Lịch sử hội thoại gần đây |
| `api_key` | `string` | No | Gemini API Key truyền từ BYOK |

#### 📤 Response Schema (JSON):
```json
{
  "status": "success",
  "answer": "Dựa trên trang slide 4, Function Calling cung cấp một 'Hợp đồng' rõ ràng dạng JSON Schema cho Agent [trang 4].\n\n🚀 **Mở rộng tri thức (Deep-dive Expansion):** Phân tích chi tiết ứng dụng...",
  "citations": [4],
  "orchestrator": {
    "branch": "followup",
    "title": "Có thể đào sâu → Mở rộng tri thức",
    "description": "Mở rộng tri thức trực tiếp trong câu trả lời LLM và chuyển tiếp sang Understanding Check.",
    "next_node": "Mở rộng tri thức → Understanding Check"
  },
  "tool_data": {
    "quiz_id": "q_1785389600",
    "quiz_type": "multiple_choice", // Hoặc "short_answer"
    "concept": "Function Calling Schema",
    "question": "Điểm khác biệt cốt lõi giữa Text-based ReAct và Function Calling là gì?",
    "options": [
      "ReAct chạy nhanh hơn Function Calling",
      "Function Calling cung cấp JSON Schema chuẩn hóa cho mô hình thay vì tự đoán văn bản",
      "ReAct không dùng được cho các mô hình AI hiện đại",
      "Function Calling không cần định nghĩa công cụ trước khi gọi"
    ],
    "correct_index": 1,
    "expected_keywords": ["schema", "hợp đồng", "json"], // Dành cho short_answer
    "explanation": "Chính xác! Function Calling giúp định nghĩa 'hợp đồng' dữ liệu rõ ràng..."
  },
  "default_suggestions": [
    "Ví dụ JSON Schema chuẩn khi định nghĩa 1 tool tra cứu tài liệu?",
    "Khi mô hình gọi sai tên Tool thì xử lý fallback ra sao?",
    "Cách test nghiệm thu Function Calling trong bài Hackathon?"
  ],
  "page": 4,
  "model_engine": "Gemini 3.1 Flash Lite"
}
```

#### 💡 Lưu ý giá trị `orchestrator.branch`:
1. `"simple_end"` ➔ Trả về `answer` + `default_suggestions` ➔ Kết thúc lượt.
2. `"clarify"` ➔ Trả về `tool_data` dạng Hỏi làm rõ (`clarifying_question`, `suggested_inputs`).
3. `"understanding_check"` ➔ Trả về `tool_data` dạng Bài Quiz kiểm tra hiểu (`quiz_type`: `"multiple_choice"` hoặc `"short_answer"`).
4. `"followup"` ➔ Trả về `answer` có phần "Mở rộng tri thức" + `tool_data` dạng Quiz kiểm tra ngay sau đó.

---

### 3.3. `POST /api/quiz/submit`
Endpoint nộp và chấm bài Quiz (Trắc nghiệm 4 lựa chọn hoặc Tự luận ngắn).

#### 📥 Request Body Schema (JSON):

**Trường hợp 1: Nộp Bài Trắc nghiệm (`multiple_choice`)**
```json
{
  "quiz_id": "q_1785389600",
  "quiz_type": "multiple_choice",
  "selected_option": 1,
  "correct_option": 1,
  "question_text": "Điểm khác biệt cốt lõi giữa Text-based ReAct và Function Calling là gì?",
  "page_number": 4
}
```

**Trường hợp 2: Nộp Bài Tự luận Ngắn (`short_answer`)**
```json
{
  "quiz_id": "q_1785389600",
  "quiz_type": "short_answer",
  "user_text_answer": "Function Calling cung cấp JSON schema chuẩn hóa",
  "expected_keywords": ["schema", "hợp đồng", "json"],
  "question_text": "Tại sao Function Calling được gọi là hợp đồng?",
  "page_number": 4
}
```

#### 📤 Response Schema (JSON):

**Khi trả lời ĐÚNG (`is_correct: true`):**
```json
{
  "is_correct": true,
  "feedback": "🎉 Xuất sắc! Bạn đã trả lời chính xác và nắm rất vững bản chất bài học. (Kết thúc lượt)",
  "next_step": "end_turn",
  "default_suggestions": [
    "Ví dụ JSON Schema chuẩn khi định nghĩa 1 tool tra cứu tài liệu?",
    "Khi mô hình gọi sai tên Tool thì xử lý fallback ra sao?",
    "Cách test nghiệm thu Function Calling trong bài Hackathon?"
  ]
}
```

**Khi trả lời SAI (`is_correct: false`):**
```json
{
  "is_correct": false,
  "feedback": "⚠️ Chưa chính xác. AI Tutor đã phân tích nguyên nhân nhầm lẫn bên dưới:",
  "next_step": "misconception_explanation",
  "misconception": {
    "misconception_point": "Học viên đang nhầm lẫn giữa dữ liệu trong Context Window và Weights của LLM.",
    "re_explanation": "💡 **Điểm cần lưu ý:** Context Window chỉ chứa dữ liệu nạp tạm thời khi gửi API request.",
    "new_example": "📌 **Ví dụ mới:** Giống như khi bạn đi thi được mang tài liệu vào phòng thi.",
    "recheck_question": {
      "quiz_id": "rq_101",
      "quiz_type": "multiple_choice",
      "concept": "Kiểm tra lại qua ví dụ mới",
      "question": "Nếu slide cập nhật trang mới, làm sao AI nắm được ngay?",
      "options": [
        "Huấn luyện lại AI",
        "Nạp trang slide mới vào Context Window khi gửi request",
        "Thay đổi System Policy",
        "Không thể"
      ],
      "correct_index": 1,
      "explanation": "Rất xuất sắc!"
    }
  },
  "default_suggestions": [
    "Ví dụ JSON Schema chuẩn khi định nghĩa 1 tool tra cứu tài liệu?",
    "Khi mô hình gọi sai tên Tool thì xử lý fallback ra sao?",
    "Cách test nghiệm thu Function Calling trong bài Hackathon?"
  ]
}
```

---

## 🛠️ 4. Hướng dẫn Tích hợp với Backend Khác (C# / Node.js / Java / Go)

Nếu hệ thống backend mới viết bằng framework khác:

1. **Khởi chạy Frontend:**
   - Frontend tĩnh nằm ở thư mục `frontend/` (bao gồm `index.html`, `styles.css`, `app.js`).
   - Có thể host tĩnh bằng Nginx, Express.js static, IIS, hoặc Live Server.

2. **Chỉnh cấu hình API Endpoint trong `frontend/app.js` (nếu khác port/domain):**
   ```javascript
   // Trong frontend/app.js, mặc định gọi endpoint tương đối:
   fetch('/api/slides')
   fetch('/api/tutor/ask')
   fetch('/api/quiz/submit')
   
   // Nếu backend host trên domain khác (ví dụ: http://my-backend.com:5000):
   const BASE_URL = "http://my-backend.com:5000";
   fetch(`${BASE_URL}/api/tutor/ask`, ...)
   ```

---

## ✅ 5. Checklist Kiểm thử Kết nối Backend

- [x] Backend phản hồi `GET /api/slides` trả ra mảng các trang slide.
- [x] Backend phản hồi `POST /api/tutor/ask` trả ra định dạng JSON khớp schema ở Mục 3.2.
- [x] Backend phản hồi `POST /api/quiz/submit` chấm đúng cả bài trắc nghiệm lẫn bài gõ tự luận ngắn.
- [x] `default_suggestions` trả về danh sách 3 từ/câu gợi ý ngắn để hiển thị thành dạng thẻ chip bấm nhanh.
