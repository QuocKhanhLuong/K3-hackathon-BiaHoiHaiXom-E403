"""Shared prompt message builder incorporating GLOBAL_SYSTEM_PROMPT and untrusted input wrappers."""

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from vlearn_ai.prompts.system import GLOBAL_SYSTEM_PROMPT


def build_trusted_messages(
    task_prompt: str,
    untrusted_payload: str,
    conversation_history: list[dict[str, Any]] | None = None,
) -> list[BaseMessage]:
    """Build trusted system message combined with task instructions and untrusted human message."""
    system_content = f"{GLOBAL_SYSTEM_PROMPT}\n\n{task_prompt}".strip()

    payload = untrusted_payload
    if conversation_history:
        history_lines = []
        for msg in conversation_history[-4:]:
            if isinstance(msg, dict):
                role = str(msg.get("role", "user"))
                content = str(msg.get("content", ""))
                history_lines.append(f"{role}: {content}")
        if history_lines:
            hist_text = "\n".join(history_lines)
            payload = (
                f"<untrusted_conversation_history>\n{hist_text}\n"
                f"</untrusted_conversation_history>\n\n{untrusted_payload}"
            )

    return [
        SystemMessage(content=system_content),
        HumanMessage(content=payload.strip()),
    ]
