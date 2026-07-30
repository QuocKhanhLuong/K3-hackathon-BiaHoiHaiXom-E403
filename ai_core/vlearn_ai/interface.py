"""Public interface for VLearn AI Core package."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from vlearn_ai.graph.builder import build_learning_graph
from vlearn_ai.graph.state import LearningLoopState
from vlearn_ai.schemas import AICoreResult


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
        initial_state: LearningLoopState = {
            "thread_id": thread_id,
            "user_query": question,
            "selected_context": selected_context,
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
        final_state = await self.app.ainvoke(initial_state, config=config)
        return self._format_result(final_state, config)

    async def resume_turn(
        self,
        *,
        thread_id: str,
        student_input: str,
    ) -> dict[str, Any]:
        """Resume an interrupted learning loop turn with student input."""
        config = {"configurable": {"thread_id": thread_id}}
        current_snapshot = self.app.get_state(config)
        curr_values = current_snapshot.values or {}

        update_values: dict[str, Any] = dict(curr_values)
        update_values["status"] = "running"

        if (
            curr_values.get("status") == "awaiting_clarification"
            or not curr_values.get("clarification_answer")
        ) and curr_values.get("route") == "clarify":
            update_values["clarification_answer"] = student_input

        if curr_values.get("status") == "awaiting_check" or curr_values.get(
            "check_question"
        ):
            update_values["student_check_answer"] = student_input

        has_native_interrupt = bool(
            current_snapshot
            and current_snapshot.tasks
            and any(t.interrupts for t in current_snapshot.tasks)
        )

        if has_native_interrupt:
            try:
                cmd = Command(resume=student_input)
                final_state = await self.app.ainvoke(cmd, config=config)
            except (RuntimeError, AttributeError, ValueError, TypeError):
                final_state = await self.app.ainvoke(update_values, config=config)
        else:
            final_state = await self.app.ainvoke(update_values, config=config)

        return self._format_result(final_state, config)

    def _format_result(
        self, state: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Format state snapshot into a stable AICoreResult dict."""
        current_values = state if isinstance(state, dict) and state else {}
        if not current_values:
            graph_state = self.app.get_state(config)
            current_values = graph_state.values if graph_state else {}

        status = current_values.get("status", "completed")
        if status == "running":
            status = "completed"

        ui_payload: dict[str, Any] | None = None
        assistant_message = current_values.get("grounded_answer")

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
