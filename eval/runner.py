"""Scenario evaluation runner executing multi-turn workflows on VLearnAICore without circular evaluation."""

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

    def _create_core_for_scenario(self, scenario: ScenarioDefinition) -> tuple[VLearnAICore, DeterministicFakeChatModel | None]:
        """Create fresh VLearnAICore instance tailored strictly to scenario offline_fixture."""
        if self.mode == "live":
            from langchain_openai import ChatOpenAI

            live_model = ChatOpenAI(
                model=self.model_name,
                api_key=self.api_key,
                temperature=0.0,
            )
            return VLearnAICore(model=live_model), None

        # Offline mode: use scenario offline_fixture (NO tag-driven route cheating!)
        script_items = []
        fault_items = []
        if scenario.offline_fixture:
            script_items = [s.model_dump() for s in scenario.offline_fixture.model_script]
            fault_items = [f.model_dump() for f in scenario.offline_fixture.faults]

        fake_model = DeterministicFakeChatModel(
            scenario_id=scenario.id,
            model_script=script_items,
            faults=fault_items,
        )
        return VLearnAICore(model=fake_model), fake_model

    async def run_scenario(
        self, scenario: ScenarioDefinition, verbose: bool = False
    ) -> ScenarioExecutionResult:
        """Run all turns in a scenario sequentially, enforcing exact start/resume semantics."""
        core, fake_model_ref = self._create_core_for_scenario(scenario)
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
            ctx_fixture = scenario.offline_fixture.context_fixture if scenario.offline_fixture else None

            context_str, retrieved_sources = self.context_provider.get_context(
                page_number=scenario.start_page,
                deck_id=scenario.deck_id,
                selected_text=selected_text,
                query=turn_def.input,
                history=conversation_history,
                context_fixture=ctx_fixture,
            )

            error_msg: str | None = None
            res: dict[str, Any] = {}
            blocked_by_previous_turn = False

            try:
                if turn_def.type == "user_turn":
                    res = await core.start_turn(
                        thread_id=thread_id,
                        question=turn_def.input,
                        selected_context=context_str,
                        conversation_history=conversation_history,
                    )
                else:  # action_response (clarification answer or check option)
                    previous_status = prev_turn_res.status if prev_turn_res else None
                    if previous_status not in {"awaiting_clarification", "awaiting_check"}:
                        blocked_by_previous_turn = True
                        res = {
                            "status": "blocked",
                            "assistant_message": None,
                            "route": None,
                            "citations": [],
                            "followups": [],
                            "tool_trace": [],
                        }
                    else:
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

            snapshot = core.app.get_state({"configurable": {"thread_id": thread_id}})
            internal_state = dict(snapshot.values or {}) if snapshot and snapshot.values else {}

            # Extract result & state fields
            status = res.get("status", "unknown")
            route_dict = res.get("route") or {}
            route_name = route_dict.get("name") if isinstance(route_dict, dict) else None

            assistant_msg = res.get("assistant_message")
            ui_payload = res.get("ui_payload") or {}

            # Action / Check details
            check_id = ui_payload.get("check_id") or ui_payload.get("id")
            action_id = res.get("action_id") or check_id
            check_q = ui_payload.get("question")
            check_opts = ui_payload.get("options") or []
            target_concept = ui_payload.get("target_concept")

            citations = res.get("citations") or []
            citation_ids = [str(c.get("citation_id", "")) for c in citations if isinstance(c, dict)]
            citation_pages = [
                int(c.get("page_number"))
                for c in citations
                if isinstance(c, dict) and c.get("page_number") is not None
            ]

            followups = res.get("followups") or []
            tool_traces = internal_state.get("tool_trace") or res.get("tool_trace") or []
            tool_sequence = [
                str(tr.get("tool")) for tr in tool_traces if isinstance(tr, dict) and tr.get("tool")
            ]

            faults_triggered = list(fake_model_ref.faults_triggered) if fake_model_ref else []

            # Public Response DTO matching frontend API
            public_response = {
                "status": status,
                "message": {"role": "assistant", "content": assistant_msg} if assistant_msg else None,
                "route": route_dict,
                "action": ui_payload if ui_payload else None,
                "citations": citations,
                "suggestions": followups,
            }

            safe_state = {
                "status": status,
                "route": route_name,
                "check_id": check_id,
                "action_id": action_id,
                "citation_ids": citation_ids,
                "retrieved_sources": retrieved_sources,
                "faults_triggered": faults_triggered,
                "error_message": error_msg,
                "grounding_valid": internal_state.get("grounding_valid"),
                "grounding_error": internal_state.get("grounding_error"),
                "grounding_failure_type": internal_state.get("grounding_failure_type"),
                "grounding_retry_count": internal_state.get("grounding_retry_count", 0),
                "grounding_invalid_citation_ids": internal_state.get("grounding_invalid_citation_ids", []),
                "grounding_uncovered_sentences": internal_state.get("grounding_uncovered_sentences", []),
                "candidate_answer": internal_state.get("candidate_answer"),
                "candidate_claims": internal_state.get("candidate_claims", []),
                "candidate_citations": internal_state.get("candidate_citations", []),
                "failure_code": internal_state.get("failure_code"),
                "failure_stage": internal_state.get("failure_stage"),
                "route_source": internal_state.get("route_source"),
            }

            response_origin = f"live_{self.model_name}" if self.mode == "live" else "scripted_fixture"

            turn_res = TurnExecutionResult(
                scenario_id=scenario.id,
                turn_index=turn_idx,
                input_type=turn_def.type,
                input_text=turn_def.input,
                route=route_name,
                route_source=internal_state.get("route_source"),
                status=status,
                assistant_message=assistant_msg,
                ui_payload=ui_payload,
                public_response=public_response,
                check_id=check_id,
                action_id=action_id,
                check_question=check_q,
                check_options=check_opts,
                target_concept=target_concept,
                citation_ids=citation_ids,
                citation_pages=citation_pages,
                followups=followups,
                tool_sequence=tool_sequence,
                tool_traces=tool_traces,
                retrieved_sources=retrieved_sources,
                faults_triggered=faults_triggered,
                error_message=error_msg,
                response_origin=response_origin,
                safe_state_snapshot=safe_state,
                latency_ms=latency_ms,
                blocked_by_previous_turn=blocked_by_previous_turn,
                grounding_valid=internal_state.get("grounding_valid"),
                grounding_error=internal_state.get("grounding_error"),
                grounding_failure_type=internal_state.get("grounding_failure_type"),
                grounding_retry_count=internal_state.get("grounding_retry_count", 0),
                grounding_invalid_citation_ids=internal_state.get("grounding_invalid_citation_ids", []),
                grounding_uncovered_sentences=internal_state.get("grounding_uncovered_sentences", []),
                candidate_answer=internal_state.get("candidate_answer"),
                candidate_claims=internal_state.get("candidate_claims", []),
                candidate_citations=internal_state.get("candidate_citations", []),
                failure_code=internal_state.get("failure_code"),
                failure_stage=internal_state.get("failure_stage"),
            )

            # Evaluate assertions
            turn_res.assertions = evaluate_turn_assertions(
                turn_res, turn_def.expected, previous_turn_res=prev_turn_res
            )

            # Fault verification: check if offline_fixture required a fault that was not triggered
            if self.mode == "offline" and scenario.offline_fixture and scenario.offline_fixture.faults and turn_idx == len(scenario.turns):
                for f in scenario.offline_fixture.faults:
                    if f.target not in faults_triggered and f.target not in tool_sequence:
                        turn_res.assertions.append(
                            AssertionResult(
                                name="fault_not_triggered",
                                passed=False,
                                message=f"Specified fault target '{f.target}' was never triggered during execution",
                                category="reliability",
                            )
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
            tier=scenario.tier,
            evaluation_type=scenario.evaluation_type,
            tags=scenario.tags,
            passed=scenario_passed,
            turn_results=turn_results,
            total_latency_ms=total_latency_ms,
            failure_reasons=failure_reasons,
        )
