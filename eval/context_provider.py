"""Context provider delivering real or synthetic slide data for evaluation without arbitrary answer injection."""

from __future__ import annotations

import re
from typing import Any

from eval.schemas import ContextFixture

try:
    from backend.app.retrieval.local_slides import LocalSlideRepository
except Exception:
    LocalSlideRepository = None  # type: ignore


class EvalContextProvider:
    """Delivers slide context and source metadata for eval runs."""

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
        deck_id: str | None = None,
        selected_text: str = "",
        query: str = "",
        history: list[dict[str, Any]] | None = None,
        max_chars: int = 12000,
        context_fixture: ContextFixture | None = None,
    ) -> tuple[str, list[str]]:
        """Return formatted course context string and list of retrieved source IDs without injecting arbitrary answers."""

        # 1. Synthetic slides fixture
        if context_fixture and context_fixture.type == "synthetic_slides" and context_fixture.slides:
            slide_dicts = [s.model_dump() for s in context_fixture.slides]
            repo = LocalSlideRepository(slides=slide_dicts) if LocalSlideRepository else None
            if repo:
                ctx = repo.build_context(
                    page_number=page_number,
                    deck_id=deck_id,
                    selected_text=selected_text,
                    query=query,
                    recent_history=history,
                    max_chars=max_chars,
                )
                sources = re.findall(r'source_id="([^"]+)"', ctx)
                return ctx, sources

            # Fallback synthetic text build
            pieces = []
            sources = []
            for slide in context_fixture.slides:
                sources.append(slide.source_id)
                pieces.append(
                    f"[source source_id=\"{slide.source_id}\" page={slide.page} deck={slide.deck_id} page_in_deck={slide.page_in_deck}]\n"
                    f"Tiêu đề: {slide.title}\n{slide.raw_text}"
                )
            if selected_text:
                pieces.insert(0, f"=== ĐOẠN HỌC VIÊN ĐÃ CHỌN ===\n{selected_text.strip()}")
            return "\n\n".join(pieces), sources

        # 2. Real slides repository
        if self.repo:
            ctx = self.repo.build_context(
                page_number=page_number,
                deck_id=deck_id,
                selected_text=selected_text,
                query=query,
                recent_history=history,
                max_chars=max_chars,
            )
            sources = re.findall(r'source_id="([^"]+)"', ctx)
            return ctx, sources

        # 3. Fallback if slide loader is missing
        fallback_ctx = (
            f"=== KHÓA HỌC: AI & LLM Foundation ===\n"
            f"[source source_id=\"d1-p{page_number}\" page={page_number} deck=d1 page_in_deck={page_number}]\n"
            f"Slide {page_number}"
        )
        if selected_text:
            fallback_ctx += f"\n\n=== ĐOẠN HỌC VIÊN ĐÃ CHỌN ===\n{selected_text}"
        return fallback_ctx, [f"d1-p{page_number}"]
