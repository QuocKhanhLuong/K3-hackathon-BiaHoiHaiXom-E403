"""Workflow module: repair misconception."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.guardrails.plan_guard import validate_plan_steps
from vlearn_ai.schemas import CheckEvaluation, RepairPlan
from vlearn_ai.tools.give_example import execute_give_example
from vlearn_ai.tools.give_hint import execute_give_hint
from vlearn_ai.tools.motivate import execute_motivate
from vlearn_ai.tools.review_concept import execute_review_concept


async def run_repair_misconception(
    check_eval: CheckEvaluation,
    context: str,
    target_concept: str,
    model: BaseChatModel,
) -> tuple[RepairPlan, str]:
    """Orchestrate allowed pedagogical tools to repair student misconception."""
    # Plan repair strategy using allowed tools
    plan_tools: list[str] = ["review_concept", "give_example"]
    if check_eval.score < 0.5:
        plan_tools = ["motivate", "give_hint", "give_example"]

    # Validate plan using plan_guard
    is_valid, _err = validate_plan_steps(plan_tools, max_steps=4)
    if not is_valid:
        plan_tools = ["review_concept", "give_example"]

    repair_plan = RepairPlan(
        tools=plan_tools,  # type: ignore
        reasoning=f"Sửa điểm nhầm '{check_eval.misconception_code}' bằng chuỗi sư phạm thích hợp.",
    )

    repair_explanation_parts: list[str] = []

    for tool in repair_plan.tools:
        if tool == "motivate":
            mot_res = await execute_motivate(
                difficulty=check_eval.error_explanation or "khái niệm khó",
                model=model,
            )
            repair_explanation_parts.append(mot_res.message)
        elif tool == "give_hint":
            hint_res = await execute_give_hint(
                topic=target_concept,
                current_state=check_eval.answer_evidence or "",
                model=model,
            )
            repair_explanation_parts.append(f"Gợi ý: {hint_res.hint}")
        elif tool == "review_concept":
            rev_res = await execute_review_concept(
                query=f"Giải thích lại điểm nhầm {check_eval.error_explanation}",
                context=context,
                model=model,
            )
            repair_explanation_parts.append(rev_res.answer)
        elif tool == "give_example":
            ex_res = await execute_give_example(
                concept=target_concept,
                context=context,
                model=model,
            )
            repair_explanation_parts.append(
                f"Ví dụ mới: {ex_res.example}\n{ex_res.explanation}"
            )

    repair_text = "\n\n".join(repair_explanation_parts)
    return repair_plan, repair_text
