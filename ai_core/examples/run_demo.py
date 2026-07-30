"""Minimal command-line demonstration for VLearn AI Core Learning Loop."""

import asyncio
import json
import uuid

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from vlearn_ai.interface import VLearnAICore


async def main():
    print("=" * 60)
    print("VLearn AI Core - Interactive Learning Loop CLI Demo")
    print("=" * 60)

    thread_id = input("Enter Thread ID (press Enter for auto-generated): ").strip()
    if not thread_id:
        thread_id = f"demo_{uuid.uuid4().hex[:8]}"

    print(f"\nUsing Thread ID: {thread_id}")

    default_context = (
        "Key (K) và Value (V) là hai khái niệm quan trọng trong cơ chế Attention. "
        "Key được dùng để so khớp độ tương đồng với Query (Q) nhằm tính ra điểm attention score. "
        "Value chứa thông tin thực tế được tổng hợp lại dựa trên trọng số attention score tương ứng."
    )

    print("\nSelect context (press Enter to use default course context):")
    print(f"Default: {default_context[:100]}...")
    selected_context = input("> ").strip()
    if not selected_context:
        selected_context = default_context

    print("\nEnter learner question:")
    print("Examples:")
    print(" 1) 'Key là gì?' (Route: simple)")
    print(" 2) 'Cái này hoạt động như thế nào?' (Route: clarify)")
    print(" 3) 'Key và Value khác nhau như thế nào?' (Route: check)")
    print(" 4) 'Tại sao attention phải chia cho căn bậc hai của d_k?' (Route: deep)")
    user_query = input("> ").strip()
    if not user_query:
        user_query = "Key và Value khác nhau như thế nào?"

    # Instantiate VLearnAICore (using fake model for demo or real if configured)
    fake_llm = FakeListChatModel(responses=[""])
    ai_core = VLearnAICore(model=fake_llm)

    print("\n" + "-" * 50)
    print("Executing start_turn()...")
    res = await ai_core.start_turn(
        thread_id=thread_id,
        question=user_query,
        selected_context=selected_context,
    )

    while True:
        print("\n" + "=" * 50)
        print(f"Current Status: {res.get('status')}")
        if res.get("route"):
            print(
                f"Route: {res['route'].get('name')} (Confidence: {res['route'].get('confidence')})"
            )
            print(f"Reason: {res['route'].get('reason')}")

        if res.get("assistant_message"):
            print(f"\nAssistant Message:\n{res['assistant_message']}")

        if res.get("ui_payload"):
            print(
                f"\nUI Payload:\n{json.dumps(res['ui_payload'], ensure_ascii=False, indent=2)}"
            )

        if res.get("citations"):
            print(f"\nCitations ({len(res['citations'])}):")
            for c in res["citations"]:
                print(f" - [{c.get('citation_id')}]: {c.get('snippet')}")

        if res.get("followups"):
            print("\nFollow-up Suggestions:")
            for idx, f in enumerate(res["followups"], 1):
                print(f" {idx}. {f.get('label')}: {f.get('question')}")

        if res.get("tool_trace"):
            print(f"\nTool Trace ({len(res['tool_trace'])} steps):")
            for t in res["tool_trace"]:
                print(f" -> {t.get('tool')} [{t.get('status')}]")

        status = res.get("status")

        if status in ("completed", "blocked", "failed"):
            print("\n" + "=" * 50)
            print(f"Turn reached terminal state: {status.upper()}")
            break

        if status == "awaiting_clarification":
            print("\n" + "-" * 50)
            ans = input("Learner Clarification Input > ").strip()
            res = await ai_core.resume_turn(thread_id=thread_id, student_input=ans)

        elif status == "awaiting_check":
            print("\n" + "-" * 50)
            ans = input("Learner Check Answer > ").strip()
            res = await ai_core.resume_turn(thread_id=thread_id, student_input=ans)

    print("\nDemo finished successfully!")


if __name__ == "__main__":
    asyncio.run(main())
