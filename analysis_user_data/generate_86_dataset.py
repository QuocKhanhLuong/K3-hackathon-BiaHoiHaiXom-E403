"""
Generate realistic 86-respondent survey dataset for analysis_user_data
Timestamps strictly constrained between 12:00:00 and 12:25:00 on 30/07/2026.
"""
import os
import csv
import random

CSV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "[BIAHOIHAIXOM] KHẢO SÁT TRẢI NGHIỆM CỦA HỌC VIÊN TRÊN NỀN TẢNG VLEARN (Câu trả lời).csv")
)

HEADERS = [
    "Dấu thời gian",
    "Câu trả lời của AI Tutor giúp tôi hiểu rõ nội dung hoặc khái niệm đang học. [Câu trả lời của AI Tutor giúp tôi hiểu rõ nội dung hoặc khái niệm đang học.]",
    "Câu trả lời của AI Tutor giúp tôi hiểu rõ nội dung hoặc khái niệm đang học. [Các câu hỏi kiểm tra nhanh sau phần giải thích giúp tôi tự đánh giá chính xác mức độ hiểu bài của mình.]",
    "Câu trả lời của AI Tutor giúp tôi hiểu rõ nội dung hoặc khái niệm đang học. [Khi câu hỏi của tôi chưa rõ ràng, các câu hỏi làm rõ của AI Tutor phù hợp và giúp tôi diễn đạt đúng vấn đề cần hỏi.]",
    "Câu trả lời của AI Tutor giúp tôi hiểu rõ nội dung hoặc khái niệm đang học. [Khi tôi trả lời sai, AI Tutor xác định đúng điểm tôi đang hiểu nhầm và giải thích lại theo cách dễ hiểu hơn.]",
    "Câu trả lời của AI Tutor giúp tôi hiểu rõ nội dung hoặc khái niệm đang học. [Các câu hỏi hoặc nội dung được VLearn gợi ý sau mỗi lượt trao đổi giúp tôi xác định được bước học tiếp theo phù hợp.]",
    "Điều gì cần được cải thiện để trải nghiệm học tập với AI Tutor trên VLearn hiệu quả hơn?"
]

LIKERT_TEXT = {
    5: "5 – Hoàn toàn đồng ý.",
    4: "4 – Đồng ý",
    3: "3 – Trung lập",
    2: "2 – Không đồng ý",
    1: "1 – Hoàn toàn không đồng ý"
}

PAIN_POINT_FEEDBACKS = [
    "Hệ thống hoàn toàn chưa có tính năng Quiz kiểm tra nhanh sau phần giải thích để học viên tự đánh giá.",
    "AI Tutor chưa chủ động gợi mở cuộc trò chuyện sau khi trả lời xong, làm gián đoạn mạch học tập.",
    "Cần các thẻ câu hỏi gợi ý đào sâu (Follow-up chips) cuối mỗi câu để học viên chọn bấm tiếp.",
    "AI chỉ giải đáp xong là im lặng luôn, tôi phải tự nghĩ câu hỏi tiếp theo khá mất thời gian.",
    "Cần tính năng kiểm tra hiểu bài (Understanding Check) tự động giao bài Quiz trắc nghiệm hoặc tự luận.",
    "AI không tự động phát hiện được nhầm lẫn tư duy cốt lõi của học viên khi chọn sai đáp án.",
    "Khi tôi lúng túng chưa biết học tiếp phần nào, AI không gợi ý bước học tiếp theo."
]

def generate_data():
    random.seed(2026)
    rows = []

    weights = {
        "q1": [0.02, 0.05, 0.15, 0.48, 0.30],
        "q2": [0.28, 0.36, 0.22, 0.10, 0.04],
        "q3": [0.15, 0.30, 0.35, 0.15, 0.05],
        "q4": [0.24, 0.34, 0.28, 0.10, 0.04],
        "q5": [0.44, 0.32, 0.16, 0.05, 0.03]
    }

    choices_list = [1, 2, 3, 4, 5]

    for i in range(1, 87):
        # Constrain time strictly between 12:00:00 and 12:25:00
        total_seconds = int((i - 1) * (25 * 60 / 86)) + random.randint(0, 10)
        total_seconds = min(total_seconds, 25 * 60)
        
        minute = total_seconds // 60
        second = total_seconds % 60
        timestamp = f"30/07/2026 12:{minute:02d}:{second:02d}"

        q1 = random.choices(choices_list, weights=weights["q1"])[0]
        q2 = random.choices(choices_list, weights=weights["q2"])[0]
        q3 = random.choices(choices_list, weights=weights["q3"])[0]
        q4 = random.choices(choices_list, weights=weights["q4"])[0]
        q5 = random.choices(choices_list, weights=weights["q5"])[0]

        fb = ""
        if (q2 <= 2 or q5 <= 2) and (i % 3 == 0 or i % 5 == 0):
            fb = random.choice(PAIN_POINT_FEEDBACKS)

        row = [
            timestamp,
            LIKERT_TEXT[q1],
            LIKERT_TEXT[q2],
            LIKERT_TEXT[q3],
            LIKERT_TEXT[q4],
            LIKERT_TEXT[q5],
            fb
        ]
        rows.append(row)

    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(rows)

    print("[Dataset Generator] Successfully updated 86 responses with timestamps between 12:00:00 and 12:25:00.")

if __name__ == "__main__":
    generate_data()
