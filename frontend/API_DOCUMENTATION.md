# 📚 VLearn Frontend API Integration Specification & Demo Setup Guide

Tài liệu hướng dẫn kết nối **Frontend UI VLearn** với hệ thống Backend REST API, bao gồm hướng dẫn thiết lập & chạy Demo chi tiết.

---

## 🚀 1. Hướng dẫn Thiết lập & Khởi chạy Demo (Quick Start Demo Guide)

### 1.1. Yêu cầu Môi trường (Prerequisites)
- **Python:** phiên bản `3.10` trở lên.
- **Thư viện phụ thuộc:** Đã cài đặt `fastapi`, `uvicorn`, `google-generativeai`, `pydantic`.
  ```powershell
  pip install fastapi uvicorn google-generativeai pydantic
  ```

---

### 1.2. Cấu hình Gemini API Key (3 Phương án)

Bạn có thể cấu hình API Key từ **Google AI Studio** (`https://aistudio.google.com/app/apikey`) theo 1 trong 3 cách:

- **Phương án A (Nhập trên Giao diện Web - Khuyên dùng):**
  - Mở web demo ➔ Bấm nút **🔑 BYOK** màu vàng ở góc trên bên phải khung chat ➔ Dán API Key vào.
- **Phương án B (Đặt biến môi trường Terminal):**
  ```powershell
  $env:GEMINI_API_KEY="AIzaSy_Key_Cua_Ban"
  ```
- **Phương án C (Chạy Demo Fallback tự động):**
  - Nếu không nạp API Key, hệ thống tự động kích hoạt bộ **Fallback sư phạm chuẩn** giúp buổi Demo mượt mà 100% không bao giờ gặp sự cố gián đoạn hay nghẽn mạng.

---

### 1.3. Lệnh Khởi chạy Server Demo
Chạy lệnh uvicorn từ thư mục gốc của dự án:
```powershell
python -m uvicorn backend.main:app --port 8000
```
> 📍 **Địa chỉ truy cập Web Demo:** `http://localhost:8000`

---

### 🎭 1.4. Kịch bản Trải nghiệm Demo Gợi ý (Demo Test Scenarios)

| Kịch bản Demo | Thao tác trên Web UI | Phản hồi của Hệ thống Multi-Agent |
|---|---|---|
| **1. Hỏi khái niệm phức tạp** | Gõ câu hỏi: *"Function Calling là gì"* | Tutor trả lời có trích dẫn `[trang 4]` ➔ Kích hoạt Tool **Understanding Check** (Bài Quiz kiểm tra hiểu). |
| **2. Thử nghiệm Quiz Tự luận** | Gõ câu trả lời vào ô text input của bài Quiz | Gemini LLM chấm bài tự luận ➔ Nếu đúng: Kết thúc lượt + 3 gợi ý đào sâu. Nếu sai: Chuyển sang Misconception Alert. |
| **3. Phát hiện nhầm lẫn (Misconception)** | Chọn sai đáp án bài Quiz | Kích hoạt Tool **Misconception Detection** ➔ Giải thích lại trúng điểm sai + ví dụ mới + Quiz phụ. |
| **4. Đào sâu tri thức** | Gõ: *"Cho ví dụ ứng dụng thực tế"* | Tutor trả lời tích hợp mục **🚀 Mở rộng tri thức** ➔ Tự động trỏ tiếp sang **Understanding Check**. |
| **5. Hỏi thiếu thông tin** | Gõ câu hỏi ngắn: *"là sao"* | Kích hoạt Tool **Hỏi làm rõ** (Clarification Tool) với 3 phương án bấm nhanh. |
| **6. Trải nghiệm bôi đen trên Slide** | Bôi đen một đoạn chữ trên Slide ➔ Bấm *"Hỏi VLearn Tutor đoạn này"* | Tutor trả lời chuẩn xác ngữ cảnh đoạn văn được chọn trên Slide. |

---

## 🌐 2. Base URL & CORS Settings

- **Default Base URL:** `http://localhost:8000`
- **Header:** `Content-Type: application/json`
- **CORS:** Backend đã bật CORS (`Access-Control-Allow-Origin: *`).

---

## 📌 3. Danh sách Các REST Endpoints

| HTTP Method | Endpoint Path | Chức năng chính |
|---|---|---|
| `GET` | `/api/slides` | Lấy danh sách toàn bộ các trang Slide bài giảng |
| `POST` | `/api/tutor/ask` | Gửi câu hỏi học viên ➔ Nhận câu trả lời + Quyết định Orchestrator + Tool Card + 3 Gợi ý |
| `POST` | `/api/quiz/submit` | Nộp bài Quiz (Trắc nghiệm hoặc Tự luận ngắn) ➔ Nhận kết quả & Misconception Alert |

---

## 📑 4. Chi tiết API Specs

### 4.1. `GET /api/slides`
Lấy dữ liệu toàn bộ các trang Slide hiển thị ở cột bên trái.

#### 📤 Response (`200 OK`):
```json
{
  "total_pages": 5,
  "slides": [
    {
      "page": 1,
      "title": "AI Product Thinking & Requirements",
      "subtitle": "AICB-P1 · Ngày 5 · Build agent xong, nhưng sản phẩm cho ai?",
      "content": "<p><b>Tên Giảng Viên:</b> VinUniversity Phase 1 Tuần 1 2026.</p><p>Giới thiệu tổng quan về tư tư duy thiết kế sản phẩm AI cho người dùng thật.</p>",
      "code": "Lecture_material_ms204v3b_r9mo78"
    }
  ]
}
```

---

### 4.2. `POST /api/tutor/ask`
Endpoint chính xử lý khi học viên nhập câu hỏi hoặc bôi đen văn bản trên slide.

#### 📥 Request Body (JSON):
```json
{
  "question": "Function Calling là gì",
  "selected_text": "Text-based ReAct vs Structured Function Calling",
  "page_number": 4,
  "chat_history": [],
  "api_key": "AIzaSy..." // Optional (BYOK)
}
```

#### 📤 Response Schema (JSON):
```json
{
  "status": "success",
  "answer": "Dựa trên trang slide 4, Function Calling cung cấp một 'Hợp đồng' rõ ràng dạng JSON Schema cho Agent [trang 4].\n\n🚀 **Mở rộng tri thức (Deep-dive Expansion):** Phân tích chi tiết...",
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
    "expected_keywords": ["schema", "hợp đồng", "json"],
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

---

### 4.3. `POST /api/quiz/submit`
Endpoint nộp và chấm bài Quiz (Trắc nghiệm hoặc Tự luận ngắn).

#### 📥 Request Body (Trắc nghiệm):
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

#### 📥 Request Body (Tự luận ngắn):
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

#### 📤 Response Schema (`is_correct: true`):
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

---

## 🛠️ 5. Hướng dẫn Tích hợp với Backend Khác

Nếu hệ thống backend mới viết bằng ngôn ngữ khác (C# / Node.js / Java / Go):
1. Đảm bảo Backend thực thi đúng các REST Endpoints đã mô tả ở Mục 4.
2. Nếu backend host ở khác port/domain, cập nhật `BASE_URL` trong `frontend/app.js`:
   ```javascript
   const BASE_URL = "http://your-backend-domain.com:5000";
   ```
