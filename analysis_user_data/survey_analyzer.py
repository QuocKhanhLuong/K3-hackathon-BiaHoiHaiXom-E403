"""
VLearn Student Experience Survey Data Analysis & Visualization Tool
Location: analysis_user_data/survey_analyzer.py
Analyzes realistic 86-respondent survey dataset.
Renders high-resolution 3-tier Likert charts (Positive, Neutral, Negative) in figures/ directory.
Moves legend outside of chart area to prevent obscuring data values.
Does NOT generate HTML files. Keeps all results local (no git push).
"""
import os
import csv
import json
from collections import Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SURVEY_CSV_NAME = "[BIAHOIHAIXOM] KHẢO SÁT TRẢI NGHIỆM CỦA HỌC VIÊN TRÊN NỀN TẢNG VLEARN (Câu trả lời).csv"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, SURVEY_CSV_NAME)
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
JSON_OUTPUT_PATH = os.path.join(BASE_DIR, "survey_metrics_summary.json")

os.makedirs(FIGURES_DIR, exist_ok=True)

def parse_likert(val_str):
    if not val_str:
        return 3
    if "5" in val_str or "Hoàn toàn đồng ý" in val_str:
        return 5
    if "4" in val_str or "Đồng ý" in val_str:
        return 4
    if "3" in val_str or "Trung lập" in val_str:
        return 3
    if "2" in val_str or "Không đồng ý" in val_str:
        return 2
    if "1" in val_str or "Hoàn toàn không đồng ý" in val_str:
        return 1
    return 3

def analyze_survey():
    if not os.path.exists(CSV_PATH):
        print(f"Error: Survey CSV not found at {CSV_PATH}")
        return None

    rows = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        for r in reader:
            if r:
                rows.append(r)

    total_responses = len(rows)

    q1_scores = [parse_likert(r[1]) for r in rows if len(r) > 1]
    q2_scores = [parse_likert(r[2]) for r in rows if len(r) > 2]
    q3_scores = [parse_likert(r[3]) for r in rows if len(r) > 3]
    q4_scores = [parse_likert(r[4]) for r in rows if len(r) > 4]
    q5_scores = [parse_likert(r[5]) for r in rows if len(r) > 5]

    def get_stats(scores):
        if not scores:
            return {"mean": 0, "count": 0, "dist": {}}
        c = Counter(scores)
        n = len(scores)
        return {
            "mean": round(sum(scores) / n, 2),
            "count": n,
            "dist": {
                "5_star": c[5],
                "4_star": c[4],
                "3_star": c[3],
                "2_star": c[2],
                "1_star": c[1]
            },
            "positive_pct": round(((c[4] + c[5]) / n) * 100, 1),
            "neutral_pct": round((c[3] / n) * 100, 1),
            "negative_pct": round(((c[1] + c[2]) / n) * 100, 1)
        }

    open_feedback = []
    for r in rows:
        if len(r) > 6 and r[6].strip():
            open_feedback.append(r[6].strip())

    summary = {
        "total_responses": total_responses,
        "primary_pain_point": {
            "dimension": "Q5: Follow-up Suggestions (Gợi mở cuộc nói chuyện)",
            "mean_score": get_stats(q5_scores)["mean"],
            "negative_pct": get_stats(q5_scores)["negative_pct"],
            "finding_summary": f"{get_stats(q5_scores)['negative_pct']}% học viên đánh giá AI Tutor thụ động, thiếu gợi mở cuộc nói chuyện hoặc gợi ý câu hỏi đào sâu."
        },
        "metrics": {
            "q1_tutor_comprehension": get_stats(q1_scores),
            "q2_quick_quiz_check": get_stats(q2_scores),
            "q3_clarification_questions": get_stats(q3_scores),
            "q4_misconception_reexplanation": get_stats(q4_scores),
            "q5_followup_suggestions": get_stats(q5_scores)
        },
        "open_feedback_comments": open_feedback,
        "feedback_count": len(open_feedback)
    }

    with open(JSON_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    generate_charts(summary)

    html_file = os.path.join(BASE_DIR, "survey_dashboard.html")
    if os.path.exists(html_file):
        os.remove(html_file)

    print(f"[Survey Analyzer] Successfully analyzed {total_responses} responses.")
    print(f"[Survey Analyzer] Primary Pain Point Q5 Mean: {summary['primary_pain_point']['mean_score']}/5.0")
    print(f"[Survey Analyzer] Figures saved to {FIGURES_DIR}")
    return summary

def generate_charts(summary):
    metrics = summary["metrics"]

    dimensions = [
        "Q1: Grounded Comprehension",
        "Q2: Quick Quiz Check",
        "Q3: Clarification Questions",
        "Q4: Misconception Detection",
        "Q5: Follow-up Suggestions (PAIN POINT)"
    ]
    means = [
        metrics["q1_tutor_comprehension"]["mean"],
        metrics["q2_quick_quiz_check"]["mean"],
        metrics["q3_clarification_questions"]["mean"],
        metrics["q4_misconception_reexplanation"]["mean"],
        metrics["q5_followup_suggestions"]["mean"]
    ]

    # --- Figure 1: Realistic Average Likert Scores ---
    plt.figure(figsize=(11, 5.5), dpi=150)
    colors = ['#ef4444' if m < 2.2 else '#f59e0b' if m < 3.2 else '#10b981' for m in means]
    bars = plt.barh(dimensions, means, color=colors, height=0.52)
    
    plt.xlim(0, 5.2)
    plt.xlabel('Average Likert Score (1 - 5)', fontsize=11, fontweight='bold')
    plt.title(f'VLearn Student Experience Survey Scores (N={summary["total_responses"]})', fontsize=13, fontweight='bold', pad=15)
    plt.axvline(x=3.0, color='#94a3b8', linestyle='--', linewidth=1, label='Baseline Threshold (3.0)')

    for bar, val in zip(bars, means):
        txt_color = '#dc2626' if val < 2.2 else '#1e293b'
        plt.text(val + 0.08, bar.get_y() + bar.get_height()/2, f'{val:.2f} / 5.0', va='center', ha='left', fontweight='bold', fontsize=10, color=txt_color)

    plt.tight_layout()
    fig1_path = os.path.join(FIGURES_DIR, "01_survey_dimension_scores.png")
    plt.savefig(fig1_path)
    plt.close()

    # --- Figure 2: Realistic 3-Tier Stacked Sentiment Breakdown (%) ---
    pos_pcts = [
        metrics["q1_tutor_comprehension"]["positive_pct"],
        metrics["q2_quick_quiz_check"]["positive_pct"],
        metrics["q3_clarification_questions"]["positive_pct"],
        metrics["q4_misconception_reexplanation"]["positive_pct"],
        metrics["q5_followup_suggestions"]["positive_pct"]
    ]
    neu_pcts = [
        metrics["q1_tutor_comprehension"]["neutral_pct"],
        metrics["q2_quick_quiz_check"]["neutral_pct"],
        metrics["q3_clarification_questions"]["neutral_pct"],
        metrics["q4_misconception_reexplanation"]["neutral_pct"],
        metrics["q5_followup_suggestions"]["neutral_pct"]
    ]
    neg_pcts = [
        metrics["q1_tutor_comprehension"]["negative_pct"],
        metrics["q2_quick_quiz_check"]["negative_pct"],
        metrics["q3_clarification_questions"]["negative_pct"],
        metrics["q4_misconception_reexplanation"]["negative_pct"],
        metrics["q5_followup_suggestions"]["negative_pct"]
    ]

    y_pos = np.arange(len(dimensions))

    plt.figure(figsize=(11, 5.8), dpi=150)
    
    # 3-tier horizontal bar plot
    p1 = plt.barh(y_pos, pos_pcts, color='#10b981', label='Positive (4-5 Stars)', height=0.5)
    p2 = plt.barh(y_pos, neu_pcts, left=pos_pcts, color='#94a3b8', label='Neutral (3 Stars)', height=0.5)
    left_neg = [p + n for p, n in zip(pos_pcts, neu_pcts)]
    p3 = plt.barh(y_pos, neg_pcts, left=left_neg, color='#ef4444', label='Negative / Pain Point (1-2 Stars)', height=0.5)

    plt.yticks(y_pos, dimensions)
    plt.xlim(0, 105)
    plt.xlabel('Percentage of Respondents (%)', fontsize=11, fontweight='bold')
    plt.title('VLearn Student Sentiment & Pain Points Breakdown (%)', fontsize=13, fontweight='bold', pad=15)
    
    # Move legend OUTSIDE below the plot box so it doesn't obstruct data
    plt.legend(bbox_to_anchor=(0.5, -0.16), loc='upper center', ncol=3, frameon=True, fontsize=10)

    # Annotate bar percentages
    for i in range(len(dimensions)):
        pos, neu, neg = pos_pcts[i], neu_pcts[i], neg_pcts[i]
        if pos >= 8:
            plt.text(pos / 2, i, f'{pos:.1f}%', va='center', ha='center', color='white', fontweight='bold', fontsize=8.5)
        if neu >= 8:
            plt.text(pos + neu / 2, i, f'{neu:.1f}%', va='center', ha='center', color='white', fontweight='bold', fontsize=8.5)
        if neg >= 8:
            plt.text(pos + neu + neg / 2, i, f'{neg:.1f}%', va='center', ha='center', color='white', fontweight='bold', fontsize=8.5)

    plt.tight_layout()
    fig2_path = os.path.join(FIGURES_DIR, "02_likert_distribution_stacked.png")
    plt.savefig(fig2_path, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    analyze_survey()
