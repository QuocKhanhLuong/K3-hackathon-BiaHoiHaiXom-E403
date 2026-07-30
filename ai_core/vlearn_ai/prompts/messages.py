"""Shared prompt message builder incorporating GLOBAL_SYSTEM_PROMPT and untrusted input wrappers."""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from vlearn_ai.prompts.system import GLOBAL_SYSTEM_PROMPT


def build_trusted_messages(
    task_prompt: str,
    untrusted_payload: str,
) -> list[BaseMessage]:
    """Build trusted system message combined with task instructions and untrusted human message."""
    system_content = f"{GLOBAL_SYSTEM_PROMPT}\n\n{task_prompt}".strip()
    return [
        SystemMessage(content=system_content),
        HumanMessage(content=untrusted_payload.strip()),
    ]
