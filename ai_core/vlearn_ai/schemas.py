"""Strict Pydantic schemas and typed exceptions for VLearn AI Core."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class InvalidGraphStateError(AICoreBaseError):
    """Raised when the graph state is in an invalid or unexpected condition."""


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


class GroundedClaim(StrictBaseModel):
    """Structured claim referencing citation IDs for verifier validation."""

    claim: str = Field(..., min_length=1)
    citation_ids: list[str] = Field(..., min_length=1)


class GroundedAnswer(StrictBaseModel):
    """Answer with embedded claims and citations."""

    answer: str = Field(..., min_length=1)
    claims: list[GroundedClaim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class ClarificationRequest(StrictBaseModel):
    """Clarification question request."""

    clarification_question: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class GiveExampleOutput(StrictBaseModel):
    """Output format for give_example tool."""

    example: str = Field(..., min_length=1)
    relevance_explanation: str = Field(..., min_length=1)


class GiveHintOutput(StrictBaseModel):
    """Output format for give_hint tool."""

    hint: str = Field(..., min_length=1)
    hint_level: int = Field(default=1, ge=1, le=3)
    guiding_question: str = Field(..., min_length=1)


class MotivateOutput(StrictBaseModel):
    """Output format for motivate tool."""

    message: str = Field(..., min_length=1)
    acknowledged_difficulty: str = Field(..., min_length=1)
    next_small_step: str = Field(..., min_length=1)


class CheckOption(StrictBaseModel):
    """Multiple choice check option."""

    option_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class MicroCheck(StrictBaseModel):
    """Understanding check question format with strict cross-field validation."""

    question: str = Field(..., min_length=1)
    question_type: Literal["multiple_choice", "short_answer"]
    target_concept: str = Field(..., min_length=1)
    expected_answer: str = Field(..., min_length=1)
    correct_option_id: str | None = None
    options: list[CheckOption] = Field(default_factory=list)
    explanation: str = Field(..., min_length=1)
    evidence: list[str] = Field(default_factory=list)
    check_id: str | None = None
    generation_signature: str | None = None

    @model_validator(mode="after")
    def validate_micro_check_fields(self) -> "MicroCheck":
        """Cross-field validation for MicroCheck MCQ vs Short Answer."""
        if not self.evidence:
            raise ValueError("Evidence must be a non-empty list of source snippets.")

        if self.question_type == "multiple_choice":
            if len(self.options) not in (3, 4):
                raise ValueError("Multiple choice questions must have 3 or 4 options.")

            opt_ids = [opt.option_id for opt in self.options]
            if len(opt_ids) != len(set(opt_ids)):
                raise ValueError("Multiple choice option IDs must be unique.")

            opt_texts = [opt.text.strip().lower() for opt in self.options]
            if len(opt_texts) != len(set(opt_texts)):
                raise ValueError("Multiple choice option texts must be unique.")

            if not self.correct_option_id:
                raise ValueError(
                    "Multiple choice questions require a non-null correct_option_id."
                )

            if self.correct_option_id not in opt_ids:
                raise ValueError(
                    f"correct_option_id '{self.correct_option_id}' does not exist in options."
                )
        else:
            # short_answer mode
            if self.options:
                raise ValueError("Short answer questions must not contain options.")
            if self.correct_option_id is not None:
                raise ValueError(
                    "Short answer questions must have null correct_option_id."
                )
            if not self.expected_answer.strip():
                raise ValueError(
                    "Short answer questions require a non-empty expected_answer."
                )

        return self


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
            "give_example",
            "give_hint",
            "motivate",
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
        "grounding_failure",
        "failure_node",
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
