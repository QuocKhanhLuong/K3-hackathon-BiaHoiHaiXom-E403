"""Prompt regressions for the shared factual grounding contract."""

from vlearn_ai.prompts.grounding_repair import GROUNDING_REPAIR_PROMPT
from vlearn_ai.prompts.pedagogical_tools import (
    GIVE_DIRECT_ANSWER_PROMPT,
    REVIEW_CONCEPT_PROMPT,
)


def test_direct_answer_prompt_requires_exact_source_ids_and_sentence_claims():
    assert "citation_id phải chính xác là source_id" in GIVE_DIRECT_ANSWER_PROMPT
    assert (
        "Mỗi câu chứa sự thật trong answer phải có một GroundedClaim"
        in GIVE_DIRECT_ANSWER_PROMPT
    )


def test_review_concept_uses_same_grounding_contract():
    assert "citation_id phải chính xác là source_id" in REVIEW_CONCEPT_PROMPT
    assert (
        "Mỗi câu chứa sự thật trong answer phải có một GroundedClaim"
        in REVIEW_CONCEPT_PROMPT
    )


def test_all_grounded_prompts_require_one_citation_per_source():
    required = "Mỗi source_id chỉ"
    assert required in GIVE_DIRECT_ANSWER_PROMPT
    assert required in REVIEW_CONCEPT_PROMPT
    assert required in GROUNDING_REPAIR_PROMPT
