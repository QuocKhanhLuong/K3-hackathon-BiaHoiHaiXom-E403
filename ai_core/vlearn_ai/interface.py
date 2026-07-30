"""VLearnAICore facade providing the public Python package API."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.types import Command

from vlearn_ai.config import get_settings
from vlearn_ai.graph.builder import build_learning_loop_graph
from vlearn_ai.guardrails.output_guard import (
    sanitize_all_output_fields,
    sanitize_output,
    sanitize_tool_trace,
)
from vlearn_ai.schemas import InvalidResumeStateError


class VLearnAICore:
    """Public facade for VLearn Learning Loop AI Core package."""

    def __init__(self, model: BaseChatModel | None = None) -> None:
        """Initialize VLearnAICore with optional chat model override for testing."""
        self.custom_model = model
        self.app = build_learning_loop_graph(model=self.custom_model)

    async def start_turn(
        self,
        *,
        thread_id: str,
        question: str,
        selected_context: str,
    ) -> dict[str, Any]:
        """Start a new turn in the learning loop for a given thread_id."""
        if not thread_id or not thread_id.strip():
            raise ValueError("thread_id must be a non-empty string.")
        if not question or not question.strip():
            raise ValueError("question must be a non-empty string.")
        if not selected_context or not selected_context.strip():
            raise ValueError("selected_context must be a non-empty string.")

        config = {"configurable": {"thread_id": thread_id}}
        settings = get_settings()

        initial_state = {
            "thread_id": thread_id,
            "user_query": question.strip(),
            "selected_context": selected_context.strip(),
            "conversation_history": [],
            "status": "running",
            "retry_count": 0,
            "tool_trace": [],
        }

        try:
            final_state = await self.app.ainvoke(
                initial_state,
                config=config,
                recursion_limit=settings.AI_RECURSION_LIMIT,
            )
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as exc:
            return self._format_error_result(thread_id, f"Execution failed: {exc}")

        return self._format_result(config, final_state)

    async def resume_turn(
        self,
        *,
        thread_id: str,
        student_input: str,
    ) -> dict[str, Any]:
        """Resume an interrupted learning loop turn with student input."""
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
                final_state = await self.app.ainvoke(
                    Command(resume=student_input.strip()),
                    config=config,
                    recursion_limit=settings.AI_RECURSION_LIMIT,
                )
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError):
                final_state = None

        if final_state is None:
            # State-based resume: update state at the paused node then continue
            update_values: dict[str, Any] = {"status": "running"}

            if curr_status == "awaiting_clarification" or curr_values.get(
                "clarification_question"
            ):
                update_values["clarification_answer"] = student_input.strip()
                as_node = "await_clarification"
            elif curr_status == "awaiting_check" or curr_values.get("check_question"):
                update_values["student_check_answer"] = student_input.strip()
                as_node = "await_check"
            else:
                as_node = None

            try:
                if as_node:
                    self.app.update_state(config, update_values, as_node=as_node)
                    final_state = await self.app.ainvoke(
                        None,
                        config=config,
                        recursion_limit=settings.AI_RECURSION_LIMIT,
                    )
                else:
                    raise InvalidResumeStateError(
                        f"Thread '{thread_id}' is in unexpected status '{curr_status}' for resume."
                    )
            except InvalidResumeStateError:
                raise
            except Exception as exc:
                raise InvalidResumeStateError(
                    f"Failed to resume thread '{thread_id}': {exc}"
                ) from exc

        return self._format_result(config, final_state)

    def _format_result(self, config: dict, state: Any) -> dict[str, Any]:
        """Format and sanitize graph output into public result dictionary."""
        graph_state = self.app.get_state(config)

        current_values = state if isinstance(state, dict) and state else {}
        if not current_values:
            current_values = graph_state.values if graph_state else {}

        status = current_values.get("status", "completed")

        route_name = current_values.get("route")
        route_conf = current_values.get("route_confidence", 0.0)
        route_reason = current_values.get("route_reason", "")
        clean_route_reason, _ = sanitize_output(route_reason)

        route_payload = None
        if route_name:
            route_payload = {
                "name": route_name,
                "confidence": route_conf,
                "reason": clean_route_reason,
            }

        ui_payload = None
        if status == "awaiting_clarification":
            clar_q = current_values.get("clarification_question")
            clean_clar_q, _ = sanitize_output(clar_q)
            ui_payload = {
                "type": "clarification_request",
                "question": clean_clar_q,
            }
        elif status == "awaiting_check":
            check_q = current_values.get("check_question") or {}
            clean_check_q, _ = sanitize_output(check_q.get("question", ""))
            clean_opts = []
            for opt in check_q.get("options") or []:
                if isinstance(opt, dict):
                    opt_text, _ = sanitize_output(str(opt.get("text", "")))
                    clean_opts.append(
                        {
                            "option_id": opt.get("option_id"),
                            "text": opt_text,
                        }
                    )
            ui_payload = {
                "type": check_q.get("question_type", "multiple_choice"),
                "question": clean_check_q,
                "options": clean_opts,
            }

        (
            clean_msg,
            _,
            _,
            clean_followups,
            clean_citations,
            clean_blocked,
        ) = sanitize_all_output_fields(
            assistant_message=current_values.get("grounded_answer"),
            followups=current_values.get("followups", []),
            citations=current_values.get("citations", []),
            blocked_reason=current_values.get("blocked_reason"),
        )

        safe_trace = sanitize_tool_trace(current_values.get("tool_trace", []))

        return {
            "status": status,
            "assistant_message": clean_msg or None,
            "route": route_payload,
            "ui_payload": ui_payload,
            "citations": clean_citations,
            "followups": clean_followups,
            "tool_trace": safe_trace,
            "blocked_reason": clean_blocked,
        }

    def _format_error_result(self, thread_id: str, error_msg: str) -> dict[str, Any]:
        """Format safe failure result."""
        clean_msg, _ = sanitize_output(error_msg)
        return {
            "status": "failed",
            "assistant_message": "Hệ thống chưa thể tạo phản hồi ổn định cho lượt này. Bạn hãy thử lại hoặc chọn lại nội dung bài học.",
            "route": None,
            "ui_payload": None,
            "citations": [],
            "followups": [],
            "tool_trace": [],
            "blocked_reason": clean_msg,
        }
