"""Public interface facade for VLearn AI Core package."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from vlearn_ai.config import get_settings
from vlearn_ai.graph.builder import build_learning_graph
from vlearn_ai.graph.state import LearningLoopState
from vlearn_ai.schemas import AICoreResult, InvalidResumeStateError


class VLearnAICore:
    """Public facade for VLearn AI Core package."""

    def __init__(
        self,
        model: BaseChatModel | None = None,
        checkpointer: Any | None = None,
    ):
        """Initialize VLearnAICore with optional custom model and checkpointer."""
        self.checkpointer = checkpointer or MemorySaver()
        self.app = build_learning_graph(model=model, checkpointer=self.checkpointer)

    async def start_turn(
        self,
        *,
        thread_id: str,
        question: str,
        selected_context: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Start a new learning loop turn."""
        if not thread_id or not thread_id.strip():
            raise ValueError("thread_id must be a non-empty string.")
        if not question or not question.strip():
            raise ValueError("question must be a non-empty string.")

        initial_state: LearningLoopState = {
            "thread_id": thread_id,
            "user_query": question,
            "selected_context": selected_context or "",
            "conversation_history": conversation_history or [],
            "citations": [],
            "route": None,
            "route_confidence": 0.0,
            "route_reason": "",
            "clarification_question": None,
            "clarification_answer": None,
            "grounded_answer": None,
            "check_question": None,
            "student_check_answer": None,
            "check_result": None,
            "last_check_result": None,
            "misconception": None,
            "repair_plan": None,
            "retry_count": 0,
            "followups": [],
            "current_tool": None,
            "tool_trace": [],
            "status": "running",
            "blocked_reason": None,
            "final_output": None,
        }

        config = {"configurable": {"thread_id": thread_id}}
        settings = get_settings()
        final_state = await self.app.ainvoke(
            initial_state,
            config=config,
            recursion_limit=settings.AI_RECURSION_LIMIT,
        )
        return self._format_result(final_state, config)

    async def resume_turn(
        self,
        *,
        thread_id: str,
        student_input: str,
    ) -> dict[str, Any]:
        """Resume an interrupted learning loop turn with student input via Command(resume=...)."""
        if not thread_id or not thread_id.strip():
            raise InvalidResumeStateError("thread_id must be a non-empty string.")
        if not student_input or not student_input.strip():
            raise InvalidResumeStateError("student_input must be a non-empty string.")

        config = {"configurable": {"thread_id": thread_id}}
        current_snapshot = self.app.get_state(config)

        if not current_snapshot or not current_snapshot.values:
            raise InvalidResumeStateError(
                f"No active thread state found for thread_id '{thread_id}'."
            )

        curr_values = current_snapshot.values or {}
        curr_status = curr_values.get("status")

        has_native_interrupt = bool(
            current_snapshot.tasks and any(t.interrupts for t in current_snapshot.tasks)
        )
        has_state_pause = curr_status in ("awaiting_clarification", "awaiting_check")

        if not has_native_interrupt and not has_state_pause:
            raise InvalidResumeStateError(
                f"Thread '{thread_id}' does not have an active interrupt awaiting resume."
            )

        settings = get_settings()
        final_state = None

        if has_native_interrupt:
            try:
                cmd = Command(resume=student_input)
                final_state = await self.app.ainvoke(
                    cmd,
                    config=config,
                    recursion_limit=settings.AI_RECURSION_LIMIT,
                )
            except (RuntimeError, AttributeError, ValueError, TypeError, KeyError):
                final_state = None

        if final_state is None:
            update_values: dict[str, Any] = dict(curr_values)
            update_values["status"] = "running"
            if (
                curr_status == "awaiting_clarification"
                or curr_values.get("route") == "clarify"
            ):
                update_values["clarification_answer"] = student_input
            if curr_status == "awaiting_check" or curr_values.get("check_question"):
                update_values["student_check_answer"] = student_input

            final_state = await self.app.ainvoke(
                update_values,
                config=config,
                recursion_limit=settings.AI_RECURSION_LIMIT,
            )

        return self._format_result(final_state, config)

    def _format_result(
        self, state: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Format state snapshot into a stable AICoreResult dict."""
        graph_state = self.app.get_state(config)
        current_values = state if isinstance(state, dict) and state else {}
        if not current_values:
            current_values = graph_state.values if graph_state else {}

        # Check native LangGraph interrupt if present
        if (
            graph_state
            and graph_state.tasks
            and any(t.interrupts for t in graph_state.tasks)
        ):
            interrupt_val = graph_state.tasks[0].interrupts[0].value
            int_type = (
                interrupt_val.get("type") if isinstance(interrupt_val, dict) else None
            )

            if int_type == "clarification_request":
                return AICoreResult(
                    status="awaiting_clarification",
                    assistant_message=interrupt_val.get("question"),
                    route={
                        "name": current_values.get("route"),
                        "confidence": current_values.get("route_confidence", 1.0),
                        "reason": current_values.get("route_reason", ""),
                    }
                    if current_values.get("route")
                    else None,
                    ui_payload=interrupt_val,
                    citations=current_values.get("citations", []),
                    followups=[],
                    tool_trace=current_values.get("tool_trace", []),
                ).model_dump()

            elif int_type in ("multiple_choice", "short_answer", "micro_check"):
                return AICoreResult(
                    status="awaiting_check",
                    assistant_message=current_values.get("grounded_answer")
                    or interrupt_val.get("question"),
                    route={
                        "name": current_values.get("route"),
                        "confidence": current_values.get("route_confidence", 1.0),
                        "reason": current_values.get("route_reason", ""),
                    }
                    if current_values.get("route")
                    else None,
                    ui_payload=interrupt_val,
                    citations=current_values.get("citations", []),
                    followups=[],
                    tool_trace=current_values.get("tool_trace", []),
                ).model_dump()

        status = current_values.get("status", "completed")
        if status == "running":
            status = "completed"

        assistant_message = current_values.get("grounded_answer")
        ui_payload: dict[str, Any] | None = None

        if status == "awaiting_clarification":
            assistant_message = current_values.get("clarification_question")
            ui_payload = {
                "type": "clarification_request",
                "question": current_values.get("clarification_question"),
            }
        elif status == "awaiting_check":
            check_q = current_values.get("check_question") or {}
            ui_payload = {
                "type": check_q.get("question_type", "multiple_choice"),
                "question": check_q.get("question"),
                "options": check_q.get("options"),
            }

        return AICoreResult(
            status=status,  # type: ignore
            assistant_message=assistant_message,
            route={
                "name": current_values.get("route"),
                "confidence": current_values.get("route_confidence", 1.0),
                "reason": current_values.get("route_reason", ""),
            }
            if current_values.get("route")
            else None,
            ui_payload=ui_payload,
            citations=current_values.get("citations", []),
            followups=current_values.get("followups", []),
            tool_trace=current_values.get("tool_trace", []),
            blocked_reason=current_values.get("blocked_reason"),
        ).model_dump()
