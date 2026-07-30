"""Workflow 4: Repair misconception based on planned tools."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.guardrails.plan_guard import validate_plan_tools
from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.prompts.repair import (
    REPAIR_SYSTEM_PROMPT,
    REPAIR_USER_PROMPT_TEMPLATE,
)
from vlearn_ai.schemas import (
    AIStructuredOutputError,
    CheckEvaluation,
    Citation,
    GroundedAnswer,
    GroundedClaim,
    RepairPlan,
)
from vlearn_ai.tools.give_example import execute_give_example
from vlearn_ai.tools.give_hint import execute_give_hint
from vlearn_ai.tools.motivate import execute_motivate
from vlearn_ai.tools.review_concept import execute_review_concept


async def run_repair_misconception(
    check_eval: CheckEvaluation,
    context: str,
    target_concept: str,
    retry_count: int,
    model: BaseChatModel,
) -> tuple[RepairPlan, GroundedAnswer, list[str]]:
    """Plan misconception repair and execute planned pedagogical tools."""
    untrusted_payload = REPAIR_USER_PROMPT_TEMPLATE.format(
        misconception_code=check_eval.misconception_code,
        error_explanation=check_eval.error_explanation,
        student_answer=check_eval.answer_evidence or "Không rõ",
        recommended_strategy=check_eval.recommended_repair_strategy,
    )
    messages = build_trusted_messages(REPAIR_SYSTEM_PROMPT, untrusted_payload)

    plan: RepairPlan | None = None
    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(RepairPlan)
            res = await structured.ainvoke(messages)
            if isinstance(res, RepairPlan):
                plan = res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"RepairPlan structured output failed: {exc}"
        ) from exc

    if not plan:
        raise AIStructuredOutputError("Failed to generate valid RepairPlan.")

    # Validate repair plan tools
    validate_plan_tools(plan.planned_tools, retry_count=retry_count)

    repair_responses: list[str] = []
    grounded_claims: list[GroundedClaim] = []
    grounded_citations: list[Citation] = []
    executed_tools: list[str] = []

    planned = list(plan.planned_tools)
    if "review_concept" not in planned:
        planned.insert(0, "review_concept")

    for tool_name in planned:
        if tool_name == "review_concept":
            r_obj = await execute_review_concept(target_concept, context, model)
            repair_responses.append(r_obj.answer)
            grounded_claims.extend(r_obj.claims)
            grounded_citations.extend(r_obj.citations)
            executed_tools.append("review_concept")
        elif tool_name == "give_example":
            ex_obj = await execute_give_example(target_concept, context, model)
            repair_responses.append(f"Ví dụ: {ex_obj.example}")
            executed_tools.append("give_example")
        elif tool_name == "give_hint":
            h_obj = await execute_give_hint(
                target_concept, context, hint_level=min(retry_count + 1, 3), model=model
            )
            repair_responses.append(
                f"Gợi ý: {h_obj.hint}\nCâu hỏi gợi mở: {h_obj.guiding_question}"
            )
            executed_tools.append("give_hint")
        elif tool_name == "motivate":
            m_obj = await execute_motivate(check_eval.error_explanation, model)
            repair_responses.append(f"Lời động viên: {m_obj.message}")
            executed_tools.append("motivate")

    combined_repair_text = "\n\n".join(repair_responses)
    grounded_repair = GroundedAnswer(
        answer=combined_repair_text or "Cần xem lại khái niệm đã học.",
        claims=grounded_claims,
        citations=grounded_citations,
    )
    return plan, grounded_repair, executed_tools
