"""Strict Pydantic schemas for VLearn AI Core."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RouteOutput(BaseModel):
    """Router decision for workflow classification."""

    route: Literal["simple", "clarify", "check", "deep"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str


class Citation(BaseModel):
    """Citation mapping to course material context."""

    citation_id: str
    snippet: str
    source_location: str | None = None


class GroundedAnswer(BaseModel):
    """Direct grounded answer with evidence and citations."""

    answer: str
    evidence: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class ClarificationRequest(BaseModel):
    """Clarification question when context or query is ambiguous."""

    clarification_question: str
    reason: str


class MicroCheck(BaseModel):
    """Micro-check question to evaluate learner understanding."""

    question: str
    question_type: Literal["multiple_choice", "short_answer"]
    target_concept: str
    expected_answer: str
    options: list[str] | None = None
    explanation: str
    evidence: list[str] = Field(default_factory=list)


class CheckEvaluation(BaseModel):
    """Evaluation of student answer and misconception detection."""

    is_correct: bool
    score: float = Field(..., ge=0.0, le=1.0)
    misconception_code: str | None = None
    error_explanation: str | None = None
    answer_evidence: str | None = None
    recommended_repair_strategy: str | None = None


class RepairPlan(BaseModel):
    """Plan for misconception repair using only allowed pedagogical tools."""

    tools: list[Literal["review_concept", "give_example", "give_hint", "motivate"]]
    reasoning: str


class FollowUp(BaseModel):
    """Suggested follow-up exploration question."""

    label: str
    question: str


class FollowUpSuggestions(BaseModel):
    """List of 2-3 suggested follow-up questions."""

    followups: list[FollowUp] = Field(default_factory=list)


class ToolTrace(BaseModel):
    """Record of pedagogical tool execution."""

    tool: str
    status: str
    prompt_version: str
    model: str
    details: dict[str, Any] | None = None


class AICoreResult(BaseModel):
    """Stable JSON-serializable output returned by VLearnAICore public interface."""

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


class InjectionAssessment(BaseModel):
    """LLM Prompt Injection Assessment output."""

    injection_detected: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    attack_types: list[
        Literal[
            "instruction_override",
            "prompt_extraction",
            "tool_manipulation",
            "data_exfiltration",
            "role_impersonation",
            "context_injection",
            "none",
        ]
    ] = Field(default_factory=lambda: ["none"])
    reason: str
    safe_user_intent: str | None = None
