"""Scenario evaluation runner executing multi-turn workflows on VLearnAICore."""

from __future__ import annotations

import os
import time
from typing import Any

from vlearn_ai.interface import VLearnAICore

from ai_core.tests.fake_model import DeterministicFakeChatModel
from eval.assertions import evaluate_turn_assertions
from eval.context_provider import EvalContextProvider
from eval.live_judge import LiveJudgeEvaluator
from eval.schemas import (
    AssertionResult,
    ScenarioDefinition,
    ScenarioExecutionResult,
    TurnExecutionResult,
)


class ScenarioRunner:
    """Executes evaluation scenarios on VLearnAICore across multiple turns."""

    def __init__(
        self,
        mode: str = "offline",
        model_name: str = "gpt-5-nano",
        api_key: str | None = None,
        use_judge: bool = False,
        context_provider: EvalContextProvider | None = None,
    ):
        self.mode = mode
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.use_judge = use_judge
        self.context_provider = context_provider or EvalContextProvider()
        self.judge = LiveJudgeEvaluator(model_name=self.model_name, api_key=self.api_key) if use_judge else None

    def _create_core_for_scenario(self, scenario: ScenarioDefinition) -> VLearnAICore:
        """Create fresh VLearnAICore instance tailored to scenario requirements."""
        if self.mode == "live":
            from langchain_openai import ChatOpenAI

            live_model = ChatOpenAI(
                model=self.model_name,
                api_key=self.api_key,
                temperature=0.0,
            )
            return VLearnAICore(model=live_model)

        # Offline mode: configure DeterministicFakeChatModel based on scenario tags and setup
        route_to_return = "simple"
        misconception_to_return = False
        is_injection = False

        tags_lower = [t.lower() for t in scenario.tags]
        scen_id_lower = scenario.id.lower()

        if any(t in tags_lower for t in ["clarify", "route_clarify"]) or "clarify" in scen_id_lower:
            route_to_return = "clarify"
        elif any(t in tags_lower for t in ["check", "route_check"]) or "check" in scen_id_lower:
            route_to_return = "check"
        elif any(t in tags_lower for t in ["deep", "route_deep"]) or "deep" in scen_id_lower:
            route_to_return = "deep"

        if "misconception" in tags_lower or "repair" in tags_lower or "repair" in scen_id_lower:
            misconception_to_return = True

        if "adversarial" in scenario.tags or "injection" in scenario.id.lower():
            is_injection = True

        fake_model = DeterministicFakeChatModel(
            route_to_return=route_to_return,
            misconception_to_return=misconception_to_return,
            is_injection=is_injection,
        )
        return VLearnAICore(model=fake_model)

    async def run_scenario(
        self, scenario: ScenarioDefinition, verbose: bool = False
    ) -> ScenarioExecutionResult:
        """Run all turns in a scenario sequentially, enforcing exact start/resume semantics."""
        core = self._create_core_for_scenario(scenario)
        thread_id = f"eval_scenario_{scenario.id}_{int(time.time() * 1000)}"

        turn_results: list[TurnExecutionResult] = []
        conversation_history: list[dict[str, Any]] = list(scenario.setup.conversation_history)
        selected_text = scenario.setup.selected_text

        scenario_passed = True
        failure_reasons: list[str] = []
        total_latency_ms = 0
        prev_turn_res: TurnExecutionResult | None = None

        for turn_idx, turn_def in enumerate(scenario.turns, start=1):
            t0 = time.time()
            context_str, retrieved_sources = self.context_provider.get_context(
                page_number=scenario.start_page,
                selected_text=selected_text,
                query=turn_def.input,
                history=conversation_history,
            )

            error_msg: str | None = None
            res: dict[str, Any] = {}

            try:
                if turn_def.type == "user_turn":
                    res = await core.start_turn(
                        thread_id=thread_id,
                        question=turn_def.input,
                        selected_context=context_str,
                        conversation_history=conversation_history,
                    )
                else:  # action_response (clarification answer or check option)
                    res = await core.resume_turn(
                        thread_id=thread_id,
                        student_input=turn_def.input,
                    )
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                res = {
                    "status": "failed",
                    "assistant_message": None,
                    "route": None,
                    "citations": [],
                    "followups": [],
                    "tool_trace": [],
                    "blocked_reason": str(exc),
                }

            latency_ms = int((time.time() - t0) * 1000)
            total_latency_ms += latency_ms

            # Extract result fields
            status = res.get("status", "unknown")
            route_dict = res.get("route") or {}
            route_name = route_dict.get("name") if isinstance(route_dict, dict) else None
            route_src = route_dict.get("reason") if isinstance(route_dict, dict) else None

            assistant_msg = res.get("assistant_message")
            citations = res.get("citations") or []
            citation_ids = [str(c.get("citation_id", "")) for c in citations if isinstance(c, dict)]
            citation_pages = [
                int(c.get("page_number"))
                for c in citations
                if isinstance(c, dict) and c.get("page_number") is not None
            ]

            followups = res.get("followups") or []
            tool_traces = res.get("tool_trace") or []
            tool_sequence = [
                str(tr.get("tool")) for tr in tool_traces if isinstance(tr, dict) and tr.get("tool")
            ]

            # Build turn result model
            turn_res = TurnExecutionResult(
                scenario_id=scenario.id,
                turn_index=turn_idx,
                input_type=turn_def.type,
                input_text=turn_def.input,
                route=route_name,
                route_source="deterministic_fallback" if "deterministic" in str(route_src).lower() else "structured_model",
                status=status,
                assistant_message=assistant_msg,
                citation_ids=citation_ids,
                citation_pages=citation_pages,
                followups=followups,
                tool_sequence=tool_sequence,
                tool_traces=tool_traces,
                retrieved_sources=retrieved_sources,
                error_message=error_msg,
                latency_ms=latency_ms,
            )

            # Evaluate assertions
            turn_res.assertions = evaluate_turn_assertions(
                turn_res, turn_def.expected, previous_turn_res=prev_turn_res
            )

            # Soft quality judge if live mode
            if self.mode == "live" and self.judge and assistant_msg:
                judge_eval = await self.judge.judge_turn_response(
                    question=turn_def.input,
                    response=assistant_msg,
                    context=context_str,
                    followups=followups,
                )
                if not judge_eval.get("judge_passed", True):
                    turn_res.assertions.append(
                        AssertionResult(
                            name="live_judge_quality",
                            passed=False,
                            message=f"Judge failed: {judge_eval.get('reason')}",
                            category="general",
                        )
                    )

            turn_res.passed = all(a.passed for a in turn_res.assertions)
            if not turn_res.passed:
                scenario_passed = False
                failed_names = [a.name for a in turn_res.assertions if not a.passed]
                failure_reasons.append(
                    f"Turn {turn_idx} failed assertions: {', '.join(failed_names)}"
                )

            turn_results.append(turn_res)
            prev_turn_res = turn_res

            # Append turn history for subsequent user turns
            conversation_history.append({"role": "user", "content": turn_def.input})
            if assistant_msg:
                conversation_history.append({"role": "assistant", "content": assistant_msg})

        return ScenarioExecutionResult(
            scenario_id=scenario.id,
            name=scenario.name,
            tags=scenario.tags,
            passed=scenario_passed,
            turn_results=turn_results,
            total_latency_ms=total_latency_ms,
            failure_reasons=failure_reasons,
        )
