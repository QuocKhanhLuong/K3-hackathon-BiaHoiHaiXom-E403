"""Grounding guardrail for verifying evidence against course context."""

from vlearn_ai.schemas import Citation


def verify_grounding(
    answer: str,
    evidence: list[str],
    citations: list[Citation],
    context: str,
) -> tuple[bool, str | None]:
    """Verify that cited evidence appears within supplied context."""
    if not context or not context.strip():
        return False, "Course context is empty. Grounding cannot be verified."

    normalized_context = " ".join(context.lower().split())

    for idx, snippet in enumerate(evidence):
        normalized_snippet = " ".join(snippet.lower().split())
        # Check if at least key tokens of snippet appear in normalized context
        if normalized_snippet and normalized_snippet not in normalized_context:
            # Check partial match (if snippet length > 20)
            if (
                len(normalized_snippet) > 20
                and normalized_snippet[:20] in normalized_context
            ):
                continue
            return (
                False,
                f"Evidence item {idx + 1} does not exist in context: '{snippet[:50]}...'",
            )

    return True, None
