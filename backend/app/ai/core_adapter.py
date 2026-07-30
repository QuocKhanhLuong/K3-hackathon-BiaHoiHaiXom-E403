"""Adapter isolating the backend from LangGraph and VLearn AI Core details."""

from __future__ import annotations

from typing import Any, NoReturn, Protocol

from backend.app.errors import AIServiceError, ConflictError
from backend.app.models import CoreInvocation


class AICorePort(Protocol):
    async def start_turn(
        self,
        *,
        thread_id: str,
        question: str,
        selected_context: str,
        conversation_history: list[dict[str, Any]],
    ) -> CoreInvocation: ...

    async def resume_turn(
        self, *, thread_id: str, student_input: str
    ) -> CoreInvocation: ...

    @property
    def available(self) -> bool: ...


class VLearnAICoreAdapter:
    """Lazy real adapter so health endpoints remain available on bad config."""

    def __init__(self, model: Any | None = None, checkpointer: Any | None = None):
        self._core: Any | None = None
        self._init_error: Exception | None = None
        try:
            from vlearn_ai import VLearnAICore

            self._core = VLearnAICore(model=model, checkpointer=checkpointer)
        except Exception as exc:  # noqa: BLE001 - availability boundary
            self._init_error = exc

    @property
    def available(self) -> bool:
        if self._core is None or self._init_error is not None:
            return False
        import os

        from vlearn_ai.config import get_settings

        settings = get_settings()
        return not (
            os.environ.get("RUN_LIVE_TESTS") != "1"
            and getattr(self._core, "custom_model", None) is None
            and not settings.OPENAI_API_KEY
        )

    def _require_core(self):
        if not self.available:
            raise AIServiceError() from self._init_error
        return self._core

    def _snapshot(self, thread_id: str) -> dict[str, Any]:
        core = self._require_core()
        snapshot = core.app.get_state({"configurable": {"thread_id": thread_id}})
        return dict(snapshot.values or {}) if snapshot else {}

    async def start_turn(
        self,
        *,
        thread_id: str,
        question: str,
        selected_context: str,
        conversation_history: list[dict[str, Any]],
    ) -> CoreInvocation:
        core = self._require_core()
        try:
            result = await core.start_turn(
                thread_id=thread_id,
                question=question,
                selected_context=selected_context,
                conversation_history=conversation_history,
            )
            return CoreInvocation(result=result, state=self._snapshot(thread_id))
        except Exception as exc:  # noqa: BLE001 - provider/domain boundary
            self._raise_mapped(exc)

    async def resume_turn(
        self, *, thread_id: str, student_input: str
    ) -> CoreInvocation:
        core = self._require_core()
        try:
            result = await core.resume_turn(
                thread_id=thread_id, student_input=student_input
            )
            return CoreInvocation(result=result, state=self._snapshot(thread_id))
        except Exception as exc:  # noqa: BLE001 - provider/domain boundary
            self._raise_mapped(exc)

    @staticmethod
    def _raise_mapped(exc: Exception) -> NoReturn:
        if exc.__class__.__name__ == "InvalidResumeStateError":
            raise ConflictError() from exc
        raise AIServiceError() from exc
