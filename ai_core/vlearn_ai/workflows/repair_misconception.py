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
    RepairExecution,
    RepairPlan,
    SupplementalActions,
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
) -> RepairExecution:
    """Plan misconception repair and execute planned pedagogical tools."""
    untrusted_payload = REPAIR_USER_PROMPT_TEMPLATE.format(
        misconception_code=check_eval.misconception_code,
        error_explanation=check_eval.error_explanation,
        student_answer=check_eval.answer_evidence or "Không rõ",
        recommended_strategy=check_eval.recommended_repair_strategy,
        retry_count=retry_count,
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

    # Grounded facts and trusted supplemental pedagogy stay separate.  A
    # hypothetical example must never affect source-scoped factual grounding.
    repair_responses: list[str] = []
    grounded_claims: list[GroundedClaim] = []
    grounded_citations: list[Citation] = []
    executed_tools: list[str] = []

    planned = list(plan.planned_tools)
    if "review_concept" not in planned:
        planned.insert(0, "review_concept")
    validate_plan_tools(planned, retry_count=retry_count)
    plan = plan.model_copy(update={"planned_tools": planned})
    supplemental = SupplementalActions()

    for tool_name in planned:
        if tool_name == "review_concept":
            r_obj = await execute_review_concept(target_concept, context, model)
            repair_responses.append(r_obj.answer)
            grounded_claims.extend(r_obj.claims)
            grounded_citations.extend(r_obj.citations)
            executed_tools.append("review_concept")
        elif tool_name == "give_example":
            supplemental = supplemental.model_copy(
                update={
                    "illustrative_example": await execute_give_example(
                        target_concept, context, model
                    )
                }
            )
            executed_tools.append("give_example")
        elif tool_name == "give_hint":
            supplemental = supplemental.model_copy(
                update={
                    "hint": await execute_give_hint(
                        target_concept,
                        context,
                        hint_level=min(retry_count + 1, 3),
                        model=model,
                    )
                }
            )
            executed_tools.append("give_hint")
        elif tool_name == "motivate":
            supplemental = supplemental.model_copy(
                update={
                    "motivation": await execute_motivate(
                        check_eval.error_explanation, model
                    )
                }
            )
            executed_tools.append("motivate")

    combined_repair_text = "\n\n".join(repair_responses)
    grounded_repair = GroundedAnswer(
        answer=combined_repair_text or "Cần xem lại khái niệm đã học.",
        claims=grounded_claims,
        citations=grounded_citations,
    )
    return RepairExecution(
        plan=plan,
        grounded_repair=grounded_repair,
        supplemental_actions=supplemental,
        executed_tools=executed_tools,
    )
