"""Local PDF slide repository and multi-slide retrieval context builder."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.slide_loader import ALL_PDF_SLIDES

ROOT_DIR = Path(__file__).resolve().parents[3]


def _score_slide(slide: dict[str, Any], query_tokens: set[str]) -> float:
    text = (str(slide.get("title", "")) + " " + str(slide.get("raw_text", ""))).lower()
    slide_tokens = set(re.findall(r"[\wÀ-ỹ]+", text))
    if not slide_tokens or not query_tokens:
        return 0.0
    overlap = slide_tokens & query_tokens
    return len(overlap) / max(len(query_tokens), 1)


class LocalSlideRepository:
    """Read the preloaded hackathon decks with multi-slide retrieval capabilities."""

    def __init__(self, slides: list[dict[str, Any]] | None = None):
        self.slides = slides if slides is not None else ALL_PDF_SLIDES

    def list_slides(self, deck: str | None = None) -> list[dict[str, Any]]:
        if deck:
            return [slide for slide in self.slides if slide.get("deck_id") == deck]
        return list(self.slides)

    def resolve(
        self, page_number: int | None, deck_id: str | None = None
    ) -> dict[str, Any] | None:
        if not self.slides:
            return None
        page = max(1, int(page_number or 1))
        target_slides = (
            [s for s in self.slides if s.get("deck_id") == deck_id]
            if deck_id
            else self.slides
        )
        if not target_slides:
            target_slides = self.slides
        return next(
            (
                slide
                for slide in target_slides
                if int(slide.get("page_in_deck", slide.get("page", -1))) == page
                or int(slide.get("page", -1)) == page
            ),
            target_slides[0] if target_slides else None,
        )

    def build_context(
        self,
        page_number: int,
        deck_id: str | None = None,
        selected_text: str = "",
        query: str = "",
        recent_history: list[dict[str, Any]] | None = None,
        max_chars: int = 12000,
    ) -> str:
        """Build multi-slide retrieval context bundle within budget.

        Strategy:
        1. Selected text (highest priority)
        2. Current slide (always included)
        3. Neighboring slides (±2 in deck)
        4. Top relevant slides in same deck
        5. Deck outline header
        6. Scope strictly to same deck
        7. Deduplicate slides
        8. Budget cap under max_chars
        """
        current_slide = self.resolve(page_number, deck_id=deck_id)
        if not current_slide and self.slides:
            current_slide = self.slides[0]

        deck_id = current_slide.get("deck_id") if current_slide else deck_id
        deck_slides = self.list_slides(deck=deck_id) if deck_id else list(self.slides)

        curr_p_in_deck = current_slide.get("page_in_deck", 1) if current_slide else 1

        # Explicit slide/page references outrank neighboring semantic retrieval.
        explicit_pages: set[int] = set()
        for match in re.finditer(r"\b(?:slide|slides|trang)\s+(\d+)(?:\s*[-–]\s*(\d+))?", query.lower()):
            start, end = int(match.group(1)), int(match.group(2) or match.group(1))
            explicit_pages.update(range(min(start, end), max(start, end) + 1))

        # Collect neighboring slides (±1 in deck)
        neighbor_pages: set[int] = set()
        for s in deck_slides:
            p_ind = int(s.get("page_in_deck", 1))
            if abs(p_ind - curr_p_in_deck) <= 1:
                neighbor_pages.add(int(s.get("page", -1)))

        # Token scoring for relevant slides in deck
        search_text = query + " " + selected_text
        if recent_history:
            for msg in recent_history[-2:]:
                if isinstance(msg, dict):
                    search_text += " " + str(msg.get("content", ""))
        q_tokens = set(re.findall(r"[\wÀ-ỹ]+", search_text.lower()))

        scored_slides = []
        for s in deck_slides:
            score = _score_slide(s, q_tokens)
            scored_slides.append((score, s))
        scored_slides.sort(key=lambda x: x[0], reverse=True)

        top_scored_pages = {int(s.get("page", -1)) for _, s in scored_slides[:2]}

        # Combine page numbers in order of priority while preserving deck flow
        ordered_pages: list[int] = []
        if current_slide:
            ordered_pages.append(int(current_slide.get("page", 1)))

        for s in deck_slides:
            page = int(s.get("page_in_deck", s.get("page", -1)))
            if page in explicit_pages and int(s.get("page", -1)) not in ordered_pages:
                ordered_pages.append(int(s.get("page", -1)))

        for s in deck_slides:
            p = int(s.get("page", -1))
            if p not in ordered_pages and (p in neighbor_pages or p in top_scored_pages):
                ordered_pages.append(p)

        # Short factual questions should remain focused unless explicit pages need more.
        if len(query.split()) <= 12 and not explicit_pages:
            ordered_pages = ordered_pages[:4]

        page_to_slide = {int(s.get("page", -1)): s for s in deck_slides}

        pieces: list[str] = []
        deck_name = (
            current_slide.get("deck_name", "Bài học") if current_slide else "Bài học"
        )
        pieces.append(
            f"=== KHÓA HỌC: {deck_name} (Tổng số slide: {len(deck_slides)}) ==="
        )

        if selected_text.strip():
            pieces.append(
                f"=== ĐOẠN HỌC VIÊN ĐÃ CHỌN (ƯU TIÊN CAO NHẤT) ===\n{selected_text.strip()}"
            )

        for p in ordered_pages:
            s = page_to_slide.get(p)
            if not s:
                continue
            source_id = f"{s.get('deck_id', 'd')}-p{s.get('page_in_deck', p)}"
            header = (
                f'[source source_id="{source_id}" page={s.get("page")} '
                f"deck={s.get('deck_id')} page_in_deck={s.get('page_in_deck')}]"
            )
            title = f"Tiêu đề: {s.get('title', '')}"
            raw = str(s.get("raw_text", ""))
            piece = f"{header}\n{title}\n{raw}"

            current_total_len = sum(len(part) for part in pieces)
            if current_total_len + len(piece) + 2 > max_chars:
                break
            pieces.append(piece)

        return "\n\n".join(pieces)

    def pdf_path_for_page(
        self, page_number: int, deck_id: str | None = None
    ) -> tuple[Path, int] | None:
        slide = self.resolve(page_number, deck_id=deck_id)
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
