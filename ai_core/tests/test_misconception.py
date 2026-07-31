"""Unit tests for misconception detection and repair planning."""

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.guardrails.plan_guard import validate_plan_tools
from vlearn_ai.prompts.repair import REPAIR_USER_PROMPT_TEMPLATE
from vlearn_ai.schemas import AIStructuredOutputError, CheckEvaluation
from vlearn_ai.workflows.detect_misconception import run_detect_misconception
from vlearn_ai.workflows.repair_misconception import run_repair_misconception


@pytest.mark.asyncio
async def test_detect_misconception_correct():
    fake_llm = DeterministicFakeChatModel(misconception_to_return=False)
    res = await run_detect_misconception(
        question="Key dùng để làm gì?",
        expected_answer="So khớp với Query",
        student_answer="So khớp với Query",
        context="Key dùng để so khớp với Query.",
        correct_option_id="opt_a",
        options=[],
        model=fake_llm,
    )
    assert res.is_correct is True
    assert res.score == 1.0


@pytest.mark.asyncio
async def test_detect_misconception_incorrect():
    fake_llm = DeterministicFakeChatModel(misconception_to_return=True)
    res = await run_detect_misconception(
        question="Key dùng để làm gì?",
        expected_answer="So khớp với Query",
        student_answer="Lưu dữ liệu",
        context="Key dùng để so khớp với Query.",
        correct_option_id="opt_a",
        options=[],
        model=fake_llm,
    )
    assert res.is_correct is False
    assert res.score == 0.0


@pytest.mark.asyncio
async def test_repair_misconception_plan_retry_zero_no_motivate():
    fake_llm = DeterministicFakeChatModel(misconception_to_return=True)
    eval_res = await run_detect_misconception(
        question="Key dùng để làm gì?",
        expected_answer="So khớp với Query",
        student_answer="Lưu dữ liệu",
        context="Key dùng để so khớp với Query.",
        correct_option_id="opt_a",
        options=[],
        model=fake_llm,
    )

    execution = await run_repair_misconception(
        check_eval=eval_res,
        context="Key dùng để so khớp với Query.",
        target_concept="Transformer Key",
        retry_count=0,
        model=fake_llm,
    )
    assert "motivate" not in execution.plan.planned_tools
    assert execution.supplemental_actions.illustrative_example is not None
    assert execution.supplemental_actions.illustrative_example.example
    assert len(execution.executed_tools) > 0
    assert execution.grounded_repair.citations


@pytest.mark.asyncio
async def test_repair_retry_can_render_hint_and_motivation_separately():
    fake_llm = DeterministicFakeChatModel(
        model_script=[
            {
                "schema": "RepairPlan",
                "output": {
                    "misconception_code": "key_value_confusion",
                    "recommended_strategy": "retry_support",
                    "planned_tools": ["motivate", "give_hint", "review_concept"],
                },
            }
        ]
    )
    execution = await run_repair_misconception(
        check_eval=CheckEvaluation(
            is_correct=False,
            score=0.0,
            misconception_code="key_value_confusion",
            error_explanation="Học viên nhầm Key và Value.",
            answer_evidence="Lưu dữ liệu",
            recommended_repair_strategy="retry_support",
        ),
        context='[source source_id="ctx_1"]\nKey dùng để so khớp với Query.',
        target_concept="Transformer Key",
        retry_count=1,
        model=fake_llm,
    )
    assert execution.supplemental_actions.hint is not None
    assert execution.supplemental_actions.motivation is not None
    assert "give_hint" in execution.executed_tools
    assert "motivate" in execution.executed_tools
    assert len(execution.executed_tools) == len(set(execution.executed_tools))


def test_repair_planner_payload_includes_retry_as_untrusted_data():
    payload = REPAIR_USER_PROMPT_TEMPLATE.format(
        misconception_code="code",
        error_explanation="error",
        student_answer="answer",
        recommended_strategy="strategy",
        retry_count=2,
    )
    assert "<untrusted_repair_input>" in payload
    assert "Số lần thử lại trước đó: 2" in payload


def test_validate_plan_tools_rejects_unsupported_tools():
    # validate_understanding is not allowed in RepairPlan
    with pytest.raises(AIStructuredOutputError):
        validate_plan_tools(["review_concept", "validate_understanding"], retry_count=1)

    # give_direct_answer is not allowed in RepairPlan
    with pytest.raises(AIStructuredOutputError):
        validate_plan_tools(["give_direct_answer", "give_example"], retry_count=1)

    # motivate forbidden on retry_count == 0
    with pytest.raises(AIStructuredOutputError):
        validate_plan_tools(["motivate", "review_concept"], retry_count=0)

    with pytest.raises(AIStructuredOutputError):
        validate_plan_tools(["review_concept", "review_concept"], retry_count=1)
