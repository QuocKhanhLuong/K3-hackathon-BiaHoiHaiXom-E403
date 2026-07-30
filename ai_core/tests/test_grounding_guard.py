"""Focused regression tests for factual structured grounding validation."""

from vlearn_ai.graph.nodes import grounding_guard_node
from vlearn_ai.guardrails.grounding_guard import (
    _context_source_ids,
    validate_grounding,
    verify_grounding,
)
from vlearn_ai.schemas import Citation, GroundedClaim

CONTEXT = """[source source_id="d1-p1" page=1 deck="day-1" page_in_deck=1]
LLM là mô hình ngôn ngữ lớn.
[source source_id="d1-p6" page=6 deck="day-1" page_in_deck=6]
Nhờ được luyện ở quy mô rộng, nó có thể xử lý nhiều tác vụ ngôn ngữ."""


def _citation(
    source_id: str = "d1-p1", snippet: str = "LLM là mô hình ngôn ngữ lớn."
) -> Citation:
    return Citation(citation_id=source_id, snippet=snippet)


def test_context_source_ids_only_accept_valid_headers():
    assert _context_source_ids(CONTEXT) == {"d1-p1", "d1-p6"}
    assert _context_source_ids('source_id="not-a-header"') == set()


def test_exact_context_source_id_and_verbatim_snippet_pass():
    valid, error = verify_grounding(
        "LLM là mô hình ngôn ngữ lớn.",
        [_citation()],
        CONTEXT,
        [GroundedClaim(claim="LLM là mô hình ngôn ngữ lớn.", citation_ids=["d1-p1"])],
    )
    assert valid is True
    assert error is None


def test_invented_or_suffixed_citation_id_fails():
    for source_id in ("citation_1", "d1-p1-slide1"):
        result = validate_grounding(
            "LLM là mô hình ngôn ngữ lớn.",
            [_citation(source_id)],
            CONTEXT,
            [
                GroundedClaim(
                    claim="LLM là mô hình ngôn ngữ lớn.", citation_ids=[source_id]
                )
            ],
        )
        assert result.valid is False
        assert result.invalid_citation_ids == [source_id]
        assert "does not exist" in result.error


def test_empty_citations_or_claims_fail_for_factual_answer():
    valid, error = verify_grounding("LLM là mô hình ngôn ngữ lớn.", [], CONTEXT, [])
    assert valid is False and "no citations" in error
    valid, error = verify_grounding(
        "LLM là mô hình ngôn ngữ lớn.", [_citation()], CONTEXT, []
    )
    assert valid is False and "no structured claims" in error


def test_paraphrased_or_absent_snippet_fails():
    result = validate_grounding(
        "LLM là mô hình ngôn ngữ lớn.",
        [_citation(snippet="LLM là một mô hình lớn.")],
        CONTEXT,
        [GroundedClaim(claim="LLM là mô hình ngôn ngữ lớn.", citation_ids=["d1-p1"])],
    )
    assert result.valid is False
    assert result.failure_type == "citation_snippet_not_in_context"


def test_unknown_claim_citation_and_unsupported_claim_fail():
    unknown = validate_grounding(
        "LLM là mô hình ngôn ngữ lớn.",
        [_citation()],
        CONTEXT,
        [GroundedClaim(claim="LLM là mô hình ngôn ngữ lớn.", citation_ids=["d1-p6"])],
    )
    assert unknown.failure_type == "unknown_claim_citation"
    unsupported = validate_grounding(
        "LLM có ý thức như con người.",
        [_citation()],
        CONTEXT,
        [GroundedClaim(claim="LLM có ý thức như con người.", citation_ids=["d1-p1"])],
    )
    assert unsupported.failure_type == "unsupported_claim"


def test_live_failure_fixture_requires_each_factual_sentence_claim():
    answer = "LLM là mô hình ngôn ngữ lớn. Nhờ được luyện ở quy mô rộng, nó có thể xử lý nhiều tác vụ ngôn ngữ."
    incomplete = validate_grounding(
        answer,
        [_citation()],
        CONTEXT,
        [GroundedClaim(claim="LLM là mô hình ngôn ngữ lớn.", citation_ids=["d1-p1"])],
    )
    assert incomplete.failure_type == "uncovered_factual_sentence"
    assert incomplete.uncovered_sentences == [
        "Nhờ được luyện ở quy mô rộng, nó có thể xử lý nhiều tác vụ ngôn ngữ."
    ]

    corrected = validate_grounding(
        answer,
        [
            _citation(),
            _citation(
                "d1-p6",
                "Nhờ được luyện ở quy mô rộng, nó có thể xử lý nhiều tác vụ ngôn ngữ.",
            ),
        ],
        CONTEXT,
        [
            GroundedClaim(claim="LLM là mô hình ngôn ngữ lớn.", citation_ids=["d1-p1"]),
            GroundedClaim(
                claim="Nhờ được luyện ở quy mô rộng, nó có thể xử lý nhiều tác vụ ngôn ngữ.",
                citation_ids=["d1-p6"],
            ),
        ],
    )
    assert corrected.valid is True


def test_guard_node_propagates_structured_diagnostics_to_state():
    invalid_id_state = grounding_guard_node(
        {
            "grounded_answer": "LLM là mô hình ngôn ngữ lớn.",
            "grounded_claims": [
                {
                    "claim": "LLM là mô hình ngôn ngữ lớn.",
                    "citation_ids": ["d1-p1-slide1"],
                }
            ],
            "citations": [
                {
                    "citation_id": "d1-p1-slide1",
                    "snippet": "LLM là mô hình ngôn ngữ lớn.",
                }
            ],
            "selected_context": CONTEXT,
            "tool_trace": [],
        }
    )
    assert invalid_id_state["grounding_invalid_citation_ids"] == ["d1-p1-slide1"]
    assert invalid_id_state["grounding_uncovered_sentences"] == []

    uncovered_state = grounding_guard_node(
        {
            "grounded_answer": "LLM là mô hình ngôn ngữ lớn. Nhờ được luyện ở quy mô rộng, nó có thể xử lý nhiều tác vụ ngôn ngữ.",
            "grounded_claims": [
                {"claim": "LLM là mô hình ngôn ngữ lớn.", "citation_ids": ["d1-p1"]}
            ],
            "citations": [
                {"citation_id": "d1-p1", "snippet": "LLM là mô hình ngôn ngữ lớn."}
            ],
            "selected_context": CONTEXT,
            "tool_trace": [],
        }
    )
    assert uncovered_state["grounding_failure_type"] == "uncovered_factual_sentence"
    assert uncovered_state["grounding_uncovered_sentences"] == [
        "Nhờ được luyện ở quy mô rộng, nó có thể xử lý nhiều tác vụ ngôn ngữ."
    ]
