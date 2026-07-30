"""VLearn AI Core CP4 Evaluation Suite.

Runs evaluation on golden_set.json using VLearnAICore.
Default mode is offline/deterministic (using DeterministicFakeChatModel).
Live eval runs ONLY when both OPENAI_API_KEY and RUN_LIVE_TESTS=1 are set.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add ai_core to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
AI_CORE_DIR = ROOT_DIR / "ai_core"
if str(AI_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_CORE_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vlearn_ai.interface import VLearnAICore

# Try importing backend slides loader for real context if available
try:
    from backend.slide_loader import ALL_PDF_SLIDES
except Exception:
    ALL_PDF_SLIDES = {}


def _get_context_for_page(page_number: int) -> str:
    """Retrieve real slide content if available, or fallback to meaningful default context."""
    if ALL_PDF_SLIDES and page_number in ALL_PDF_SLIDES:
        return ALL_PDF_SLIDES[page_number]
    return (
        f"Nội dung bài học slide trang {page_number}: Kiến thức về Transformer, "
        "mô hình tự chú ý (Self-Attention), cơ chế Key (K), Query (Q), và Value (V). "
        "Key dùng để so khớp với Query. Value chứa thông tin nội dung."
    )


async def run_eval():
    golden_set_path = Path(__file__).parent / "golden_set.json"
    if not golden_set_path.exists():
        print(f"Error: Golden set not found at {golden_set_path}")
        return

    with open(golden_set_path, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    total = len(golden_set)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    run_live = os.environ.get("RUN_LIVE_TESTS", "") == "1"

    is_live = bool(api_key and run_live)
    mode_str = "LIVE (GPT-5-nano)" if is_live else "OFFLINE/DETERMINISTIC (FakeModel)"

    print("\n========================================================")
    print("  VLearn AI Core CP4 Evaluation Suite")
    print(f"  Mode: {mode_str}")
    print(f"  Test Cases: {total}")
    print("========================================================\n")

    if is_live:
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            model=os.environ.get("OPENAI_EVAL_MODEL", "gpt-5-nano"),
            api_key=api_key,
            temperature=0.0,
        )
        ai_core = VLearnAICore(model=model)
    else:
        from tests.fake_model import DeterministicFakeChatModel

        fake_model = DeterministicFakeChatModel()
        ai_core = VLearnAICore(model=fake_model)

    results = []
    correct_route_count = 0
    grounding_pass_count = 0
    blocked_policy_count = 0
    multiturn_complete_count = 0
    failure_count = 0
    total_latency_ms = 0

    for idx, case in enumerate(golden_set):
        case_id = case["id"]
        question = case["question"]
        page_num = case.get("page_number", 1)
        expected_route = case.get("expected_route", "simple")
        context = _get_context_for_page(page_num)

        thread_id = f"eval_thread_{case_id}"
        print(f"[{idx + 1}/{total}] Testing {case_id}: '{question[:50]}...'")

        t0 = time.time()
        notes = []
        passed = True

        try:
            # Handle multi-turn or previous question if specified
            if "previous_question" in case:
                prev_q = case["previous_question"]
                res_prev = await ai_core.start_turn(
                    thread_id=thread_id,
                    question=prev_q,
                    selected_context=context,
                )
                if res_prev.get("status") in (
                    "awaiting_clarification",
                    "awaiting_check",
                ):
                    await ai_core.resume_turn(
                        thread_id=thread_id,
                        student_input="Trả lời câu hỏi trước.",
                    )

            # Main turn execution
            res = await ai_core.start_turn(
                thread_id=thread_id,
                question=question,
                selected_context=context,
            )

            # If graph paused at clarification or check, perform resume turn
            if res.get("status") in ("awaiting_clarification", "awaiting_check"):
                resume_input = (
                    "opt_a"
                    if res.get("status") == "awaiting_check"
                    else "Tôi muốn giải thích thêm"
                )
                res = await ai_core.resume_turn(
                    thread_id=thread_id,
                    student_input=resume_input,
                )

            latency_ms = int((time.time() - t0) * 1000)
            total_latency_ms += latency_ms

            status = res.get("status", "unknown")
            route_dict = res.get("route") or {}
            actual_route = route_dict.get("name", "unknown")
            assistant_msg = res.get("assistant_message") or ""

            # Check route accuracy
            route_matched = (
                actual_route == expected_route
                or (
                    expected_route == "simple"
                    and actual_route in ("simple", "grounded_answer")
                )
                or (
                    expected_route == "clarify"
                    and actual_route in ("clarify", "simple")
                )
            )
            if route_matched:
                correct_route_count += 1
            else:
                passed = False
                notes.append(
                    f"Route mismatch: expected {expected_route}, got {actual_route}"
                )

            # Check assistant message requirement for completed status
            if status == "completed" and not assistant_msg.strip():
                passed = False
                notes.append("Empty assistant message on completed status")

            if status == "failed":
                failure_count += 1
                passed = False
                notes.append(f"Turn failed: {res.get('failure_code')}")

            if status == "blocked":
                blocked_policy_count += 1

            if len(res.get("citations", [])) > 0:
                grounding_pass_count += 1

            if "previous_question" in case and status == "completed":
                multiturn_complete_count += 1

            result_entry = {
                "id": case_id,
                "question": question,
                "expected_route": expected_route,
                "actual_route": actual_route,
                "status": status,
                "passed": passed,
                "latency_ms": latency_ms,
                "notes": "; ".join(notes) if notes else "PASS",
            }

        except Exception as exc:
            latency_ms = int((time.time() - t0) * 1000)
            failure_count += 1
            result_entry = {
                "id": case_id,
                "question": question,
                "expected_route": expected_route,
                "actual_route": "ERROR",
                "status": "failed",
                "passed": False,
                "latency_ms": latency_ms,
                "notes": f"Exception: {exc}",
            }

        results.append(result_entry)
        pass_str = "✅ PASS" if result_entry["passed"] else "❌ FAIL"
        print(
            f"   -> Result: {pass_str} | Route: {result_entry['actual_route']} | Status: {result_entry['status']}"
        )

        # Only sleep in live mode to prevent rate limits
        if is_live:
            await asyncio.sleep(2)

    # Save results to eval/results/
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    results_json_path = out_dir / "results.json"
    report_md_path = out_dir / "report.md"
    legacy_md_path = Path(__file__).parent / "eval_results.md"

    pass_count = sum(1 for r in results if r["passed"])
    accuracy = (pass_count / total) * 100 if total > 0 else 0.0
    avg_latency = (total_latency_ms / total) if total > 0 else 0

    summary_data = {
        "mode": mode_str,
        "total_cases": total,
        "passed_cases": pass_count,
        "accuracy_percent": round(accuracy, 2),
        "route_accuracy_count": correct_route_count,
        "grounding_pass_count": grounding_pass_count,
        "blocked_policy_count": blocked_policy_count,
        "failure_count": failure_count,
        "average_latency_ms": round(avg_latency, 2),
        "results": results,
    }

    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    report_content = f"""# Bảng Kết Quả Đánh Giá VLearn Tutor (Native LangGraph Engine)

**Mode**: {mode_str}
**Kết quả**: {pass_count} / {total} ({accuracy:.1f}%)
**Thời gian phản hồi trung bình**: {avg_latency:.0f} ms
**Số lượt thất bại (Failure count)**: {failure_count}

| ID | Question | Expected Route | Actual Route | Status | Pass/Fail | Notes |
|---|---|---|---|---|---|---|
"""
    for r in results:
        pass_mark = "✅ PASS" if r["passed"] else "❌ FAIL"
        q_safe = r["question"].replace("\n", " ")[:60]
        report_content += f"| {r['id']} | {q_safe} | {r['expected_route']} | {r['actual_route']} | {r['status']} | {pass_mark} | {r['notes']} |\n"

    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    with open(legacy_md_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print("\n========================================================")
    print(f"  Eval Completed! Result: {pass_count}/{total} ({accuracy:.1f}%)")
    print(f"  Report written to {report_md_path}")
    print("========================================================\n")


if __name__ == "__main__":
    asyncio.run(run_eval())
