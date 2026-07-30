"""Strict Pydantic schemas and typed exceptions for VLearn AI Core."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =====================================================================
# Typed Exceptions
# =====================================================================


class AICoreBaseError(Exception):
    """Base exception for VLearn AI Core errors."""


class AIModelInvocationError(AICoreBaseError):
    """Raised when an LLM call fails completely."""


class AIStructuredOutputError(AICoreBaseError):
    """Raised when LLM fails to produce valid structured output."""


class GroundingValidationError(AICoreBaseError):
    """Raised when grounding check fails validation."""


class InvalidResumeStateError(AICoreBaseError):
    """Raised when attempting resume_turn on an invalid or un-interrupted thread state."""


# =====================================================================
# Base Model with Forbidden Extra Fields
# =====================================================================


class StrictBaseModel(BaseModel):
    """Strict base model forbidding extra fields."""

    model_config = ConfigDict(extra="forbid")


# =====================================================================
# Domain & Workflow Models
# =====================================================================


class RouteOutput(StrictBaseModel):
    """Structured classification output from router node."""

    route: Literal["simple", "clarify", "check", "deep"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., min_length=1)


class Citation(StrictBaseModel):
    """Citation referencing grounded course context."""

    citation_id: str = Field(..., min_length=1)
    snippet: str = Field(..., min_length=1)
    source_location: str | None = None


class GroundedAnswer(StrictBaseModel):
    """Answer with embedded citations."""

    answer: str = Field(..., min_length=1)
    citations: list[Citation] = Field(default_factory=list)


class ClarificationRequest(StrictBaseModel):
    """Clarification question request."""

    clarification_question: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class CheckOption(StrictBaseModel):
    """Multiple choice check option."""

    option_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class MicroCheck(StrictBaseModel):
    """Understanding check question format."""

    question: str = Field(..., min_length=1)
    question_type: Literal["multiple_choice", "short_answer"]
    target_concept: str = Field(..., min_length=1)
    expected_answer: str = Field(..., min_length=1)
    correct_option_id: str | None = None
    options: list[CheckOption] = Field(default_factory=list)
    explanation: str = Field(..., min_length=1)
    evidence: list[str] = Field(default_factory=list)

    @field_validator("options")
    @classmethod
    def validate_mcq_options(
        cls, options: list[CheckOption], info: Any
    ) -> list[CheckOption]:
        # Validate unique option IDs for multiple choice
        ids = [opt.option_id for opt in options]
        if len(ids) != len(set(ids)):
            raise ValueError("Option IDs must be unique.")
        return options


class CheckEvaluation(StrictBaseModel):
    """Evaluation of student check answer."""

    is_correct: bool
    score: float = Field(..., ge=0.0, le=1.0)
    misconception_code: str = Field(..., min_length=1)
    error_explanation: str = Field(..., min_length=1)
    answer_evidence: str | None = None
    recommended_repair_strategy: str = Field(..., min_length=1)


class RepairPlan(StrictBaseModel):
    """Planned repair steps for misconception."""

    misconception_code: str = Field(..., min_length=1)
    recommended_strategy: str = Field(..., min_length=1)
    planned_tools: list[
        Literal[
            "review_concept",
            "give_direct_answer",
            "give_example",
            "motivate",
            "give_hint",
            "validate_understanding",
        ]
    ] = Field(..., min_length=1)


class FollowUp(StrictBaseModel):
    """Follow-up suggestion item."""

    label: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)


class FollowUpSuggestions(StrictBaseModel):
    """Suggested follow-up questions."""

    followups: list[FollowUp] = Field(..., min_length=2, max_length=3)


class ToolTrace(StrictBaseModel):
    """Execution trace of a pedagogical tool or workflow node."""

    tool: Literal[
        "input_guard",
        "context_guard",
        "router",
        "ask_clarification",
        "review_concept",
        "give_direct_answer",
        "give_example",
        "motivate",
        "give_hint",
        "validate_understanding",
        "detect_misconception",
        "repair_misconception",
        "suggest_followups",
        "output_guard",
        "grounding_guard",
    ]
    status: Literal["success", "blocked", "failed", "awaiting"]
    prompt_version: str = Field(default="1.0.0")
    model: str = Field(..., min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class InjectionAssessment(StrictBaseModel):
    """Prompt injection guard assessment result."""

    injection_detected: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., min_length=1)


class AICoreResult(StrictBaseModel):
    """Final public result returned by VLearnAICore."""

    status: Literal[
        "running",
        "awaiting_clarification",
        "awaiting_check",
        "completed",
        "blocked",
        "failed",
    ]
    assistant_message: str | None = None
    route: dict[str, Any] | None = None
    ui_payload: dict[str, Any] | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    followups: list[dict[str, Any]] = Field(default_factory=list)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
    blocked_reason: str | None = None
