# Standalone Student Experience Survey Data Analysis Tool (`analysis_user_data/`)

---

## 📁 Cấu trúc Thư mục `analysis_user_data/`

- **`[BIAHOIHAIXOM] KHẢO SÁT TRẢI NGHIỆM CỦA HỌC VIÊN TRÊN NỀN TẢNG VLEARN (Câu trả lời).csv`**: Bộ dữ liệu khảo sát gồm **86 mẫu trả lời**
- **`survey_analyzer.py`**: Tool Python tính toán các chỉ số thống kê và tự động vẽ biểu đồ dạng hình ảnh PNG.
- **`survey_metrics_summary.json`**: Tệp tổng hợp chỉ số thống kê JSON.
- **`figures/`**: Thư mục lưu các biểu đồ hình ảnh PNG trực quan:
  - `01_survey_dimension_scores.png`: Biểu đồ so sánh điểm trung bình Likert giữa 5 tiêu chí (Làm nổi bật Pain Point ở các câu hỏi).
  - `02_likert_distribution_stacked.png`: Biểu đồ tỷ lệ đồng ý / không đồng ý (Sentiment Breakdown %).

---

## 🚀 Cách chạy Tool trên Local

```powershell
python analysis_user_data/survey_analyzer.py
```
