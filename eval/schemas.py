"""Strict Pydantic schemas for scenarios, turn expectations, assertion results, and reports."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    min_followups: int | None = None
    max_followups: int | None = None

    assistant_message_required: bool | None = None
    grounding_required: bool | None = None
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
    tags: list[str] = Field(default_factory=list)
    mode: Literal["offline", "live", "both"] = "both"
    deck_id: str = "d1"
    start_page: int = 1
    setup: ScenarioSetup = Field(default_factory=ScenarioSetup)
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
    citation_ids: list[str] = Field(default_factory=list)
    citation_pages: list[int] = Field(default_factory=list)
    followups: list[dict[str, Any]] = Field(default_factory=list)
    tool_sequence: list[str] = Field(default_factory=list)
    tool_traces: list[dict[str, Any]] = Field(default_factory=list)
    assertions: list[AssertionResult] = Field(default_factory=list)
    passed: bool = True
    latency_ms: int = 0
    retrieved_sources: list[str] = Field(default_factory=list)
    error_message: str | None = None


class ScenarioExecutionResult(BaseModel):
    """Execution output and aggregate results for a full scenario."""

    scenario_id: str
    name: str
    tags: list[str]
    passed: bool
    turn_results: list[TurnExecutionResult]
    total_latency_ms: int = 0
    failure_reasons: list[str] = Field(default_factory=list)
