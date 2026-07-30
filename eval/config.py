"""Configuration settings and path definitions for VLearn Evaluation Framework."""

from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
ROOT_DIR = EVAL_DIR.parent
SCENARIOS_DIR = EVAL_DIR / "scenarios"
RESULTS_DIR = EVAL_DIR / "results"
FIXTURES_DIR = EVAL_DIR / "fixtures"

DEFAULT_OFFLINE_MODEL = "deterministic-fake-chat-model"
DEFAULT_LIVE_MODEL = "gpt-5-nano"

# Quality blacklists and heuristics for follow-up evaluation
GENERIC_FOLLOWUP_PATTERNS = [
    "bạn có muốn tìm hiểu thêm",
    "bạn còn câu hỏi nào không",
    "có câu hỏi gì nữa không",
    "bạn có hiểu không",
    "bạn có thắc mắc gì không",
]

# Infrastructure tools excluded from allowed_tools strict check
INFRASTRUCTURE_TOOLS = [
    "input_guard",
    "context_guard",
    "output_guard",
    "grounding_guard",
]

# Standard categories for failure grouping
FAILURE_CATEGORIES = [
    "routing",
    "tool_selection",
    "tool_order",
    "grounding",
    "citation",
    "followup",
    "state_leak",
    "interrupt_resume",
    "repair",
    "retrieval",
    "provider",
    "exception",
    "latency",
]
