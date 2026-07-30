"""Prompts package initialization."""

from vlearn_ai.prompts.clarification import CLARIFICATION_PROMPT_VERSION
from vlearn_ai.prompts.followups import FOLLOWUPS_PROMPT_VERSION
from vlearn_ai.prompts.misconception import MISCONCEPTION_PROMPT_VERSION
from vlearn_ai.prompts.pedagogical_tools import PEDAGOGICAL_TOOLS_PROMPT_VERSION
from vlearn_ai.prompts.repair import REPAIR_PROMPT_VERSION
from vlearn_ai.prompts.router import (
    ROUTER_PROMPT_VERSION,
    ROUTER_SYSTEM_PROMPT,
    ROUTER_USER_PROMPT_TEMPLATE,
)
from vlearn_ai.prompts.system import SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION
from vlearn_ai.prompts.understanding_check import CHECK_PROMPT_VERSION

__all__ = [
    "CHECK_PROMPT_VERSION",
    "CLARIFICATION_PROMPT_VERSION",
    "FOLLOWUPS_PROMPT_VERSION",
    "MISCONCEPTION_PROMPT_VERSION",
    "PEDAGOGICAL_TOOLS_PROMPT_VERSION",
    "REPAIR_PROMPT_VERSION",
    "ROUTER_PROMPT_VERSION",
    "ROUTER_SYSTEM_PROMPT",
    "ROUTER_USER_PROMPT_TEMPLATE",
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_VERSION",
]
