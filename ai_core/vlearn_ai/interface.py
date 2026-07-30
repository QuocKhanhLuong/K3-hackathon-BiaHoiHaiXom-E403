"""VLearnAICore facade providing the public Python package API."""

import json
import logging
import time
from pathlib import Path
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
from vlearn_ai.schemas import AICoreBaseError, InvalidResumeStateError

logger = logging.getLogger("vlearn_ai")

# ---------------------------------------------------------------------------
# Conversation history sanitization
# ---------------------------------------------------------------------------
_MAX_HISTORY_LENGTH = 20
_MAX_MESSAGE_CHARS = 2000
_ALLOWED_HISTORY_FIELDS = {"role", "content"}
_ALLOWED_ROLES = {"user", "assistant"}


def _normalize_conversation_history(
    raw: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    """Normalize and sanitize conversation history into safe list."""
    if not raw:
        return []
    safe: list[dict[str, str]] = []
    for item in raw[-_MAX_HISTORY_LENGTH:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in _ALLOWED_ROLES or not content:
            continue
        safe.append({
            "role": role,
            "content": content[:_MAX_MESSAGE_CHARS],
        })
    return safe


# ---------------------------------------------------------------------------
# Transient state reset — prevents old turn leaking into new one
# ---------------------------------------------------------------------------
_TRANSIENT_FIELDS: dict[str, Any] = {
    "route": None,
    "route_confidence": 0.0,
    "route_reason": "",
    "clarification_question": None,
    "clarification_answer": None,
    "grounded_answer": None,
    "grounded_claims": [],
    "citations": [],
    "grounding_valid": None,
    "grounding_error": None,
    "grounding_failure_type": None,
    "abstention_message": None,
    "check_question": None,
    "student_check_answer": None,
    "check_result": None,
    "misconception": None,
    "repair_plan": None,
    "retry_count": 0,
    "followups": [],
    "blocked_reason": None,
    "failure_code": None,
    "failure_stage": None,
    "final_output": None,
    "tool_trace": [],
    "current_tool": None,
    "context_truncated": False,
    "context_injection_detected": False,
    "context_injection_patterns": [],
}


# ---------------------------------------------------------------------------
# JSONL Logging
# ---------------------------------------------------------------------------
def _log_interaction(entry: dict[str, Any]) -> None:
    """Append one JSON line to the persistent AI log file."""
    try:
        settings = get_settings()
        log_dir = Path(getattr(settings, "AI_LOG_DIR", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "ai_interactions.jsonl"
        safe_entry = {
            k: v
            for k, v in entry.items()
            if k
            not in (
                "raw_prompt",
                "api_key",
                "OPENAI_API_KEY",
                "system_prompt",
            )
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(safe_entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        logger.debug("Failed to write AI log entry", exc_info=True)


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
        conversation_history: list[dict[str, Any]] | None = None,
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
        safe_history = _normalize_conversation_history(conversation_history)

        # Build initial state with ALL transient fields explicitly reset
        initial_state: dict[str, Any] = {
            **_TRANSIENT_FIELDS,
            "thread_id": thread_id,
            "user_query": question.strip(),
            "selected_context": selected_context.strip(),
            "conversation_history": safe_history,
            "status": "running",
        }

        t0 = time.time()
        try:
            final_state = await self.app.ainvoke(
                initial_state,
                config=config,
                recursion_limit=settings.AI_RECURSION_LIMIT,
            )
        except AICoreBaseError:
            raise
        except Exception as exc:
            _log_interaction({
                "event": "start_turn_error",
                "thread_id": thread_id,
                "error_type": type(exc).__name__,
                "latency_ms": int((time.time() - t0) * 1000),
            })
            return self._format_error_result(
                thread_id, "start_turn", type(exc).__name__
            )

        result = self._format_result(config, final_state)
        _log_interaction({
            "event": "start_turn",
            "thread_id": thread_id,
            "status": result.get("status"),
            "route": result.get("route", {}).get("name") if result.get("route") else None,
            "tool_count": len(result.get("tool_trace", [])),
            "latency_ms": int((time.time() - t0) * 1000),
        })
        return result

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
            current_snapshot.tasks
            and any(t.interrupts for t in current_snapshot.tasks)
        )
        has_state_pause = curr_status in ("awaiting_clarification", "awaiting_check")

        if not has_native_interrupt and not has_state_pause:
            raise InvalidResumeStateError(
                f"Thread '{thread_id}' does not have an active interrupt awaiting resume."
            )

        settings = get_settings()
        final_state = None
        t0 = time.time()

        # Attempt 1: native Command(resume=...)
        if has_native_interrupt:
            try:
                final_state = await self.app.ainvoke(
                    Command(resume=student_input.strip()),
                    config=config,
                    recursion_limit=settings.AI_RECURSION_LIMIT,
                )
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError):
                final_state = None

        # Attempt 2: state-update + ainvoke(None) fallback
        if final_state is None and has_state_pause:
            update_values: dict[str, Any] = {"status": "running"}
            if curr_status == "awaiting_clarification":
                update_values["clarification_answer"] = student_input.strip()
                as_node = "await_clarification"
            elif curr_status == "awaiting_check":
                update_values["student_check_answer"] = student_input.strip()
                as_node = "await_check"
            else:
                raise InvalidResumeStateError(
                    f"Thread '{thread_id}' is in unexpected status '{curr_status}'."
                )

            try:
                self.app.update_state(config, update_values, as_node=as_node)
                final_state = await self.app.ainvoke(
                    None,
                    config=config,
                    recursion_limit=settings.AI_RECURSION_LIMIT,
                )
            except InvalidResumeStateError:
                raise
            except Exception as exc:
                _log_interaction({
                    "event": "resume_turn_error",
                    "thread_id": thread_id,
                    "error_type": type(exc).__name__,
                    "latency_ms": int((time.time() - t0) * 1000),
                })
                raise InvalidResumeStateError(
                    f"Failed to resume thread '{thread_id}': {type(exc).__name__}"
                ) from exc

        if final_state is None:
            raise InvalidResumeStateError(
                f"Thread '{thread_id}' resume produced no result."
            )

        result = self._format_result(config, final_state)
        _log_interaction({
            "event": "resume_turn",
            "thread_id": thread_id,
            "status": result.get("status"),
            "latency_ms": int((time.time() - t0) * 1000),
        })
        return result

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
                    clean_opts.append({
                        "option_id": opt.get("option_id"),
                        "text": opt_text,
                    })
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

    def _format_error_result(
        self, thread_id: str, stage: str, error_type: str
    ) -> dict[str, Any]:
        """Format safe failure result."""
        return {
            "status": "failed",
            "assistant_message": (
                "Hệ thống chưa thể tạo phản hồi ổn định cho lượt này. "
                "Bạn hãy thử lại hoặc chọn lại nội dung bài học."
            ),
            "route": None,
            "ui_payload": None,
            "citations": [],
            "followups": [],
            "tool_trace": [],
            "blocked_reason": None,
            "failure_code": error_type,
            "failure_stage": stage,
        }
