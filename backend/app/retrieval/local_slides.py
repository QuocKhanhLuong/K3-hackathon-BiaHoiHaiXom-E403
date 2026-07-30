"""Local PDF slide repository and deterministic Phase 1 context builder."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.slide_loader import ALL_PDF_SLIDES

ROOT_DIR = Path(__file__).resolve().parents[3]


class LocalSlideRepository:
    """Read the preloaded hackathon decks without exposing filesystem paths."""

    def __init__(self, slides: list[dict[str, Any]] | None = None):
        self.slides = slides if slides is not None else ALL_PDF_SLIDES

    def list_slides(self, deck: str | None = None) -> list[dict[str, Any]]:
        if deck:
            return [slide for slide in self.slides if slide.get("deck_id") == deck]
        return list(self.slides)

    def resolve(self, page_number: int | None) -> dict[str, Any] | None:
        if not self.slides:
            return None
        page = max(1, int(page_number or 1))
        return next(
            (
                slide
                for slide in self.slides
                if int(slide.get("page", -1)) == page
            ),
            None,
        )

    def build_context(self, page_number: int, selected_text: str = "", question: str = "") -> str:
        slide = self.resolve(page_number)
        pieces: list[str] = []
        if slide:
            pieces.extend(
                [
                    (
                        f"[source page={slide.get('page')} deck={slide.get('deck_id')} "
                        f"page_in_deck={slide.get('page_in_deck')}]"
                    ),
                    f"Tiêu đề: {slide.get('title', '')}",
                    f"Phụ đề: {slide.get('subtitle', '')}",
                    str(slide.get("raw_text", "")),
                ]
            )

        if question.strip():
            # Very simple stopword removal and tokenization
            words = [w.lower() for w in re.findall(r'\b\w+\b', question) if len(w) > 3]
            if words:
                scored_slides = []
                for s in self.slides:
                    if int(s.get("page", -1)) == page_number:
                        continue # Already included
                    
                    text = (s.get("title", "") + " " + s.get("raw_text", "")).lower()
                    score = sum(1 for w in words if w in text)
                    if score > 0:
                        scored_slides.append((score, s))
                
                # Take top 1 relevant slide
                scored_slides.sort(key=lambda x: x[0], reverse=True)
                for score, related_slide in scored_slides[:1]:
                    pieces.append("--- THÔNG TIN THÊM TỪ SLIDE KHÁC ---")
                    pieces.append(f"[source page={related_slide.get('page')} deck={related_slide.get('deck_id')}]")
                    pieces.append(f"Tiêu đề: {related_slide.get('title', '')}")
                    pieces.append(str(related_slide.get("raw_text", "")))

        if selected_text.strip():
            pieces.append(f"Đoạn học viên chọn: {selected_text.strip()}")
        return "\n\n".join(piece for piece in pieces if piece).strip()

    def pdf_path_for_page(self, page_number: int) -> tuple[Path, int] | None:
        slide = self.resolve(page_number)
        code = str((slide or {}).get("code", ""))
        if "#page=" not in code:
            return None
        filename, page_text = code.split("#page=", 1)
        filename = Path(filename).name
        pdf_path = (ROOT_DIR / "data" / "vlearn-pack" / "slides" / filename).resolve()
        slides_dir = (ROOT_DIR / "data" / "vlearn-pack" / "slides").resolve()
        if slides_dir not in pdf_path.parents:
            return None
        return pdf_path, int(page_text) - 1
