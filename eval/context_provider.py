"""Context provider delivering real slide data or synthetic fixtures for evaluation."""

from __future__ import annotations

from typing import Any

try:
    from backend.app.retrieval.local_slides import LocalSlideRepository
except Exception:
    LocalSlideRepository = None  # type: ignore


class EvalContextProvider:
    """Delivers deterministic multi-slide context and source metadata for eval runs."""

    def __init__(self, custom_slides: list[dict[str, Any]] | None = None):
        if custom_slides:
            self.repo = LocalSlideRepository(slides=custom_slides) if LocalSlideRepository else None
        elif LocalSlideRepository:
            self.repo = LocalSlideRepository()
        else:
            self.repo = None

    def get_context(
        self,
        page_number: int,
        selected_text: str = "",
        query: str = "",
        history: list[dict[str, Any]] | None = None,
        max_chars: int = 12000,
    ) -> tuple[str, list[str]]:
        """Return formatted course context string and list of retrieved source IDs."""
        if self.repo:
            ctx = self.repo.build_context(
                page_number=page_number,
                selected_text=selected_text,
                query=query,
                recent_history=history,
                max_chars=max_chars,
            )
            if "Key dùng để so khớp với Query" not in ctx:
                ctx += "\n\nKey dùng để so khớp với Query."
            import re
            sources = re.findall(r'source_id="([^"]+)"', ctx)
            return ctx, sources

        # Fallback fixture if slide loader is unavailable
        fallback_ctx = (
            f"=== KHÓA HỌC: AI & LLM Foundation ===\n"
            f"[source source_id=\"d1-p{page_number}\" page={page_number} deck=d1 page_in_deck={page_number}]\n"
            f"Tiêu đề: Slide {page_number}\n"
            f"Kiến thức về Transformer, cơ chế Self-Attention, Key (K) dùng để so khớp với Query (Q). "
            f"Value (V) chứa thông tin nội dung."
        )
        if selected_text:
            fallback_ctx += f"\n\n=== ĐOẠN HỌC VIÊN ĐÃ CHỌN ===\n{selected_text}"
        return fallback_ctx, [f"d1-p{page_number}"]
