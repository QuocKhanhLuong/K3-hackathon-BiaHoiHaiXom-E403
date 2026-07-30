"""CLI Interactive Demo for VLearn AI Core Learning Loop."""

import argparse
import asyncio
import json
import os
import sys

# Ensure ai_core and tests are importable when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../tests")))

from fake_model import DeterministicFakeChatModel
from vlearn_ai import VLearnAICore


async def run_demo(use_mock: bool = True):
    print("=" * 65)
    print(" 🚀 VLearn AI Core - Interactive Learning Loop Demo")
    print(
        f" Mode: {'MOCK (Offline Test Double)' if use_mock else 'REAL (OpenAI gpt-5-nano)'}"
    )
    print("=" * 65)

    model = DeterministicFakeChatModel(route_to_return="check") if use_mock else None
    ai_core = VLearnAICore(model=model)
    thread_id = "demo_thread_1"

    context = (
        "Trong kiến trúc Transformer, cơ chế Self-Attention tính toán trọng số chú ý giữa các từ. "
        "Key (K) dùng để so khớp với Query (Q) để xác định điểm tương quan, "
        "Value (V) chứa thông tin nội dung được tổng hợp dựa trên trọng số chú ý đó."
    )
    question = "Key và Value khác nhau như thế nào trong Transformer?"

    print(f"\n[Turn 1] Starting turn with question:\n  '{question}'")
    res1 = await ai_core.start_turn(
        thread_id=thread_id,
        question=question,
        selected_context=context,
    )

    print(f"\nStatus: {res1['status']}")
    print(f"Route: {res1['route']}")
    print(f"Assistant Message:\n{res1['assistant_message']}")
    if res1.get("ui_payload"):
        print(
            f"UI Payload:\n{json.dumps(res1['ui_payload'], ensure_ascii=False, indent=2)}"
        )

    if res1["status"] == "awaiting_check":
        print("\n" + "-" * 65)
        print("[Turn 2] Resuming turn with student check answer: 'opt_a'")
        res2 = await ai_core.resume_turn(
            thread_id=thread_id,
            student_input="opt_a",
        )

        print(f"\nStatus: {res2['status']}")
        print(f"Assistant Message:\n{res2['assistant_message']}")
        if res2.get("followups"):
            print("\nSuggested Follow-ups:")
            for idx, f in enumerate(res2["followups"], 1):
                print(f"  {idx}. [{f['label']}] {f['question']}")

        print("\nTool Execution Trace:")
        for t in res2.get("tool_trace", []):
            print(f"  - {t['tool']}: {t['status']}")

    print("\n" + "=" * 65)
    print(" 🎉 Demo finished successfully!")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run VLearn AI Core Demo")
    parser.add_argument("--real", action="store_true", help="Run with real OpenAI API")
    args = parser.parse_args()

    asyncio.run(run_demo(use_mock=not args.real))
