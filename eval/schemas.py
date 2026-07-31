"""Strict Pydantic schemas for scenarios, turn expectations, assertion results, metrics, and reports."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScriptedOutput(BaseModel):
    """Scripted LLM structured output for offline model fixture."""

    model_config = ConfigDict(extra="forbid")

    schema_name: str = Field(..., alias="schema")
    output: dict[str, Any]


class FaultDefinition(BaseModel):
    """Fault injection specification for offline testing."""

    model_config = ConfigDict(extra="forbid")

    target: str
    type: Literal[
        "raise",
        "timeout",
        "invalid_structured_output",
        "empty_output",
        "unsupported_citation",
        "duplicate_check",
        "generic_followups",
    ]
    exception: str | None = None


class ContextSlideFixture(BaseModel):
    """Custom slide definition for synthetic context fixture."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    deck_id: str = "d1"
    page: int
    page_in_deck: int = 1
    title: str = ""
    raw_text: str


class ContextFixture(BaseModel):
    """Context bundle specification for offline testing."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["real_slides", "synthetic_slides"] = "real_slides"
    slides: list[ContextSlideFixture] = Field(default_factory=list)


class OfflineFixture(BaseModel):
    """Complete offline scenario fixture independent from expected expectations."""

    model_config = ConfigDict(extra="forbid")

    model_script: list[ScriptedOutput] = Field(default_factory=list)
    faults: list[FaultDefinition] = Field(default_factory=list)
    context_fixture: ContextFixture = Field(default_factory=ContextFixture)


class TurnExpectations(BaseModel):
    """Expectations for a single turn in a test scenario."""

    model_config = ConfigDict(extra="forbid")

    routes: list[str] | None = None
    statuses: list[str] | None = None
    required_tools: list[str] | None = None
    allowed_tools: list[str] | None = None
    forbidden_tools: list[str] | None = None
    expected_tool_order: list[list[str]] | None = None

    min_citations: int | None = None
    max_citations: int | None = None
    expected_citation_pages: list[int] | None = None
    required_source_ids: list[str] | None = None
    forbidden_source_ids: list[str] | None = None
    required_deck_ids: list[str] | None = None
    forbidden_deck_ids: list[str] | None = None

    min_followups: int | None = None
    max_followups: int | None = None
    followup_schema_required: bool | None = None
    followups_unique: bool | None = None
    followups_not_duplicate_query: bool | None = None
    followups_not_duplicate_answer: bool | None = None
    generic_followups_forbidden: bool | None = None

    assistant_message_required: bool | None = None
    grounding_required: bool | None = None
    expected_grounding_valid: bool | None = None
    expected_answerability: (
        Literal["course_grounded", "general_knowledge", "insufficient_context"] | None
    ) = None
    required_citation_ids: list[str] | None = None
    forbidden_citation_ids: list[str] | None = None
    expected_grounding_retry_count: int | None = None
    required_retrieval_order_prefix: list[str] | None = None
    new_check_required: bool | None = None
    no_stale_citations: bool | None = None
    no_duplicate_action: bool | None = None

    max_tool_calls: int | None = None
    max_latency_ms: int | None = None

    expected_failure_code: str | None = None
    expected_blocked: bool | None = None

    response_contains_any: list[str] | None = None
    response_contains_all: list[str] | None = None
    response_not_contains: list[str] | None = None


class ScenarioTurn(BaseModel):
    """Single turn definition in a scenario."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["user_turn", "action_response"]
    input: str
    expected: TurnExpectations = Field(default_factory=TurnExpectations)


class ScenarioSetup(BaseModel):
    """Initial conversation setup."""

    model_config = ConfigDict(extra="forbid")

    selected_text: str = ""
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)


class ScenarioDefinition(BaseModel):
    """Complete scenario definition file model."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    tier: Literal["gold", "coverage", "exploratory"] = "gold"
    evaluation_type: Literal["hard", "exploratory"] = "hard"
    tags: list[str] = Field(default_factory=list)
    mode: Literal["offline", "live", "both"] = "both"
    deck_id: str = "d1"
    start_page: int = 1
    setup: ScenarioSetup = Field(default_factory=ScenarioSetup)
    offline_fixture: OfflineFixture | None = None
    turns: list[ScenarioTurn]

    @field_validator("id")
    @classmethod
    def validate_scenario_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Scenario ID must be non-empty.")
        return v.strip()


class AssertionResult(BaseModel):
    """Result of a single assertion check."""

    name: str
    passed: bool
    message: str
    category: str = "general"


class TurnExecutionResult(BaseModel):
    """Execution output and assertion results for one turn."""

    scenario_id: str
    turn_index: int
    input_type: str
    input_text: str
    route: str | None = None
    route_source: str | None = None
    status: str
    assistant_message: str | None = None
    ui_payload: dict[str, Any] | None = None
    public_response: dict[str, Any] | None = None
    check_id: str | None = None
    action_id: str | None = None
    check_question: str | None = None
    check_options: list[dict[str, Any]] | None = Field(default_factory=list)
    target_concept: str | None = None
    citation_ids: list[str] = Field(default_factory=list)
    citation_pages: list[int] = Field(default_factory=list)
    followups: list[dict[str, Any]] = Field(default_factory=list)
    tool_sequence: list[str] = Field(default_factory=list)
    tool_traces: list[dict[str, Any]] = Field(default_factory=list)
    assertions: list[AssertionResult] = Field(default_factory=list)
    passed: bool = True
    latency_ms: int = 0
    retrieved_sources: list[str] = Field(default_factory=list)
    faults_triggered: list[str] = Field(default_factory=list)
    error_message: str | None = None
    response_origin: str = "scripted_fixture"
    safe_state_snapshot: dict[str, Any] = Field(default_factory=dict)
    blocked_by_previous_turn: bool = False
    grounding_valid: bool | None = None
    grounding_error: str | None = None
    grounding_failure_type: str | None = None
    grounding_retry_count: int = 0
    grounding_invalid_citation_ids: list[str] = Field(default_factory=list)
    grounding_uncovered_sentences: list[str] = Field(default_factory=list)
    answerability: (
        Literal["course_grounded", "general_knowledge", "insufficient_context"] | None
    ) = None
    answerability_code: str | None = None
    source_mode: Literal["course", "model_knowledge", "none"] | None = None
    candidate_answer: str | None = None
    candidate_claims: list[dict[str, Any]] = Field(default_factory=list)
    candidate_citations: list[dict[str, Any]] = Field(default_factory=list)
    failure_code: str | None = None
    failure_stage: str | None = None


class ScenarioExecutionResult(BaseModel):
    """Execution output and aggregate results for a full scenario."""

    scenario_id: str
    name: str
    tier: str = "gold"
    evaluation_type: str = "hard"
    tags: list[str]
    passed: bool
    turn_results: list[TurnExecutionResult]
    total_latency_ms: int = 0
    failure_reasons: list[str] = Field(default_factory=list)


class MetricValue(BaseModel):
    """Explicit metric output handling zero-denominator status gracefully."""

    value: float | None = None
    evaluated_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    status: Literal["evaluated", "not_evaluated"] = "not_evaluated"
