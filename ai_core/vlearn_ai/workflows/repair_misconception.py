"""Workflow 4: Repair misconception."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from vlearn_ai.guardrails.plan_guard import validate_plan_tools
from vlearn_ai.prompts.repair import (
    REPAIR_SYSTEM_PROMPT,
    REPAIR_USER_PROMPT_TEMPLATE,
)
from vlearn_ai.schemas import CheckEvaluation, RepairPlan
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
) -> tuple[RepairPlan, str, list[str]]:
    """Run repair misconception workflow and return plan, repair text, and list of executed tool names."""
    messages = [
        SystemMessage(content=REPAIR_SYSTEM_PROMPT),
        HumanMessage(
            content=REPAIR_USER_PROMPT_TEMPLATE.format(
                misconception_code=check_eval.misconception_code,
                error_explanation=check_eval.error_explanation,
                retry_count=retry_count,
                target_concept=target_concept,
                selected_context=context,
            )
        ),
    ]

    plan: RepairPlan | None = None
    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(RepairPlan)
            res = await structured.ainvoke(messages)
            if isinstance(res, RepairPlan):
                plan = res
    except (AttributeError, ValueError, TypeError, KeyError):
        plan = None

    if plan is None:
        # Fallback plan based on retry_count rule: motivate ONLY when retry_count > 0
        planned_tools = (
            ["motivate", "review_concept", "give_example"]
            if retry_count > 0
            else ["review_concept", "give_example"]
        )
        plan = RepairPlan(
            misconception_code=check_eval.misconception_code,
            recommended_strategy=check_eval.recommended_repair_strategy,
            planned_tools=planned_tools,  # type: ignore
        )

    # Filter out motivate if retry_count == 0 to enforce rule
    if retry_count == 0 and "motivate" in plan.planned_tools:
        plan.planned_tools = [t for t in plan.planned_tools if t != "motivate"]
        if not plan.planned_tools:
            plan.planned_tools = ["review_concept", "give_example"]

    is_valid, _validation_error = validate_plan_tools(list(plan.planned_tools))
    if not is_valid:
        safe_tools = (
            ["motivate", "review_concept", "give_example"]
            if retry_count > 0
            else ["review_concept", "give_example"]
        )
        plan = RepairPlan(
            misconception_code=check_eval.misconception_code,
            recommended_strategy=check_eval.recommended_repair_strategy,
            planned_tools=safe_tools,  # type: ignore[arg-type]
        )

    parts: list[str] = []
    executed_tools: list[str] = []

    for tool_name in plan.planned_tools:
        if tool_name == "motivate":
            mot_res = await execute_motivate(
                difficulty=check_eval.error_explanation, model=model
            )
            parts.append(f"💪 {mot_res.message}")
            executed_tools.append("motivate")

        elif tool_name == "review_concept":
            rev_res = await execute_review_concept(
                query=f"Khắc phục nhầm lẫn: {check_eval.error_explanation}",
                context=context,
                model=model,
            )
            parts.append(f"📚 {rev_res.answer}")
            executed_tools.append("review_concept")

        elif tool_name == "give_example":
            ex_res = await execute_give_example(
                concept=target_concept, context=context, model=model
            )
            parts.append(f"💡 Ví dụ: {ex_res.example}")
            executed_tools.append("give_example")

        elif tool_name == "give_hint":
            hint_res = await execute_give_hint(
                concept=target_concept,
                context=context,
                hint_level=retry_count + 1,
                model=model,
            )
            parts.append(f"🔍 Gợi ý: {hint_res.hint}")
            executed_tools.append("give_hint")

    repair_text = (
        "\n\n".join(parts)
        if parts
        else "Chúng ta cùng giải thích lại khái niệm này nhé."
    )
    return plan, repair_text, executed_tools
