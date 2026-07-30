"""LangGraph workflow node implementations using native interrupt() with Python 3.10 fallback."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.types import interrupt

from vlearn_ai.config import get_settings
from vlearn_ai.graph.state import LearningLoopState
from vlearn_ai.guardrails.context_guard import check_context_safety
from vlearn_ai.guardrails.grounding_guard import verify_grounding
from vlearn_ai.guardrails.input_guard import assess_input_injection
from vlearn_ai.guardrails.output_guard import (
    sanitize_all_output_fields,
    sanitize_output,
)
from vlearn_ai.model import get_fast_model, get_generation_model
from vlearn_ai.prompts.router import ROUTER_SYSTEM_PROMPT, ROUTER_USER_PROMPT_TEMPLATE
from vlearn_ai.schemas import (
    CheckEvaluation,
    CheckOption,
    Citation,
    MicroCheck,
    RouteOutput,
)
from vlearn_ai.tools.give_direct_answer import execute_give_direct_answer
from vlearn_ai.tools.give_example import execute_give_example
from vlearn_ai.tools.review_concept import execute_review_concept
from vlearn_ai.workflows.ask_clarification import run_ask_clarification
from vlearn_ai.workflows.check_understanding import run_check_understanding
from vlearn_ai.workflows.detect_misconception import run_detect_misconception
from vlearn_ai.workflows.repair_misconception import run_repair_misconception
from vlearn_ai.workflows.suggest_followups import run_suggest_followups


def _record_trace(
    state: LearningLoopState,
    tool: str,
    status: str = "success",
    details: dict | None = None,
) -> list[dict]:
    trace = list(state.get("tool_trace", []))
    trace.append(
        {
            "tool": tool,
            "status": status,
            "prompt_version": "1.0.0",
            "model": get_settings().OPENAI_MODEL,
            "details": details or {},
        }
    )
    return trace


async def input_guard_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 1: Input guard checking initial query for prompt injection attacks."""
    query = state.get("user_query", "")
    llm = model or get_fast_model()

    assessment = await assess_input_injection(query, llm)
    if assessment.injection_detected:
        return {
            "status": "blocked",
            "blocked_reason": f"Prompt injection blocked: {assessment.reason}",
            "tool_trace": _record_trace(
                state, "input_guard", "blocked", {"reason": assessment.reason}
            ),
        }

    return {"status": "running"}


async def context_guard_node(state: LearningLoopState) -> dict[str, Any]:
    """Node 2: Context guard verifying course context length and safety."""
    context = state.get("selected_context", "")
    cfg = get_settings()

    res = check_context_safety(context, max_chars=cfg.AI_CONTEXT_MAX_CHARS)
    return {
        "selected_context": res["context"],
        "context_truncated": res["context_truncated"],
        "context_injection_detected": res["context_injection_detected"],
        "status": "running",
    }


async def router_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 3: Router node classifying query into 1 of 4 routes."""
    query = state.get("user_query", "")
    context = state.get("selected_context", "")
    llm = model or get_fast_model()

    prompt = f"{ROUTER_SYSTEM_PROMPT}\n\n" + ROUTER_USER_PROMPT_TEMPLATE.format(
        selected_context=context, user_query=query
    )

    route_out: RouteOutput | None = None
    try:
        if hasattr(llm, "with_structured_output"):
            structured = llm.with_structured_output(RouteOutput)
            res = await structured.ainvoke(prompt)
            if isinstance(res, RouteOutput):
                route_out = res
    except (AttributeError, ValueError, TypeError, KeyError):
        route_out = None

    if route_out is None:
        # Rules-based fallback heuristic classification
        q_lower = query.lower()
        if "cái này hoạt động" in q_lower or len(context.strip()) < 10:
            r, c, reason = "clarify", 0.9, "Context or query ambiguous"
        elif "khác nhau" in q_lower or "so sánh" in q_lower:
            r, c, reason = "check", 0.85, "Conceptual check question"
        elif "tại sao" in q_lower or "chi tiết" in q_lower:
            r, c, reason = "deep", 0.85, "Deep dive question"
        else:
            r, c, reason = "simple", 0.9, "Simple factual question"
        route_out = RouteOutput(route=r, confidence=c, reason=reason)

    return {
        "route": route_out.route,
        "route_confidence": route_out.confidence,
        "route_reason": route_out.reason,
        "tool_trace": _record_trace(
            state, "router", "success", {"route": route_out.route}
        ),
    }


async def generate_clarification_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 4A: Generate clarification question (no interrupt)."""
    query = state.get("user_query", "")
    context = state.get("selected_context", "")
    llm = model or get_fast_model()

    req = await run_ask_clarification(query, context, llm)
    return {
        "clarification_question": req.clarification_question,
        "status": "awaiting_clarification"
        if not state.get("clarification_answer")
        else "running",
        "tool_trace": _record_trace(state, "ask_clarification", "success"),
    }


def await_clarification_node(state: LearningLoopState) -> dict[str, Any]:
    """Node 4B: Native interrupt pausing graph for clarification answer."""
    question = state.get("clarification_question")
    resumed_input = None
    try:
        resumed_input = interrupt(
            {
                "type": "clarification_request",
                "question": question,
            }
        )
    except RuntimeError:
        resumed_input = state.get("clarification_answer")

    if not resumed_input:
        return {
            "status": "awaiting_clarification",
            "clarification_question": question,
        }

    return {
        "clarification_answer": str(resumed_input),
        "status": "running",
    }


async def guard_clarification_input_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 4C: Guard prompt injection on resumed clarification answer."""
    clar_ans = state.get("clarification_answer", "")
    llm = model or get_fast_model()

    assessment = await assess_input_injection(clar_ans, llm)
    if assessment.injection_detected:
        return {
            "status": "blocked",
            "blocked_reason": f"Prompt injection in clarification answer: {assessment.reason}",
            "tool_trace": _record_trace(
                state, "input_guard", "blocked", {"reason": assessment.reason}
            ),
        }

    return {"status": "running"}


async def grounded_answer_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 5: Produce grounded answer using direct answer or review concept tool."""
    query = state.get("user_query", "")
    if state.get("clarification_answer"):
        query = f"{query} (Làm rõ: {state.get('clarification_answer')})"

    context = state.get("selected_context", "")
    route = state.get("route", "simple")
    llm = model or get_generation_model()

    if route == "simple":
        ans_obj = await execute_give_direct_answer(query, context, llm)
        tool_used = "give_direct_answer"
    else:
        ans_obj = await execute_review_concept(query, context, llm)
        tool_used = "review_concept"

        if route == "check":
            ex_obj = await execute_give_example(query, context, llm)
            ans_obj.answer = f"{ans_obj.answer}\n\nVí dụ: {ex_obj.example}"

    citations_list = [c.model_dump() for c in ans_obj.citations]

    return {
        "grounded_answer": ans_obj.answer,
        "citations": citations_list,
        "tool_trace": _record_trace(state, tool_used, "success"),
    }


async def grounding_guard_node(state: LearningLoopState) -> dict[str, Any]:
    """Node 6: Grounding guard verifying citations against context."""
    answer = state.get("grounded_answer", "")
    citations_data = state.get("citations", [])
    context = state.get("selected_context", "")

    citations = [Citation(**c) for c in citations_data if isinstance(c, dict)]
    is_valid, err_msg = verify_grounding(answer, citations, context)

    return {
        "grounding_valid": is_valid,
        "grounding_error": err_msg,
        "status": "running",
        "tool_trace": _record_trace(
            state, "grounding_guard", "success" if is_valid else "failed"
        ),
    }


async def generate_check_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 7A: Generate understanding check question (no interrupt)."""
    context = state.get("selected_context", "")
    grounded_ans = state.get("grounded_answer", "")
    llm = model or get_generation_model()

    micro_check = (
        MicroCheck(**state["check_question"])
        if state.get("check_question")
        else await run_check_understanding(context, grounded_ans, llm)
    )

    return {
        "check_question": micro_check.model_dump(),
        "student_check_answer": state.get("student_check_answer"),
        "check_result": None,
        "status": "awaiting_check"
        if not state.get("student_check_answer")
        else "running",
        "tool_trace": _record_trace(state, "validate_understanding", "success"),
    }


def await_check_node(state: LearningLoopState) -> dict[str, Any]:
    """Node 7B: Native interrupt pausing graph for student check answer."""
    check_q = state.get("check_question") or {}
    resumed_answer = None
    try:
        resumed_answer = interrupt(
            {
                "type": check_q.get("question_type", "multiple_choice"),
                "question": check_q.get("question"),
                "options": check_q.get("options"),
            }
        )
    except RuntimeError:
        resumed_answer = state.get("student_check_answer")

    if not resumed_answer:
        return {
            "status": "awaiting_check",
            "check_question": check_q,
        }

    return {
        "student_check_answer": str(resumed_answer),
        "status": "running",
    }


async def guard_check_input_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 7C: Guard prompt injection on resumed student check answer."""
    student_ans = state.get("student_check_answer", "")
    llm = model or get_fast_model()

    assessment = await assess_input_injection(student_ans, llm)
    if assessment.injection_detected:
        return {
            "status": "blocked",
            "blocked_reason": f"Prompt injection in check answer: {assessment.reason}",
            "tool_trace": _record_trace(
                state, "input_guard", "blocked", {"reason": assessment.reason}
            ),
        }

    return {"status": "running"}


async def evaluate_check_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 7D: Evaluate resumed student check answer against question."""
    context = state.get("selected_context", "")
    check_q = state.get("check_question") or {}
    student_ans = state.get("student_check_answer", "")
    llm = model or get_generation_model()

    raw_options = check_q.get("options") or []
    typed_options = [CheckOption(**opt) for opt in raw_options if isinstance(opt, dict)]

    eval_res = await run_detect_misconception(
        question=check_q.get("question", ""),
        expected_answer=check_q.get("expected_answer", ""),
        student_answer=student_ans,
        context=context,
        correct_option_id=check_q.get("correct_option_id"),
        options=typed_options,
        model=llm,
    )

    return {
        "check_result": eval_res.model_dump(),
        "status": "running",
        "tool_trace": _record_trace(state, "validate_understanding", "success"),
    }


async def misconception_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 8: Detect misconception and execute repair plan."""
    context = state.get("selected_context", "")
    check_result_dict = state.get("check_result") or {}
    retry = state.get("retry_count", 0)
    llm = model or get_generation_model()

    eval_obj = (
        CheckEvaluation(**check_result_dict)
        if check_result_dict
        else CheckEvaluation(
            is_correct=False,
            score=0.0,
            misconception_code="concept_confusion",
            error_explanation="Chưa nắm vững kiến thức kiểm tra.",
            answer_evidence=state.get("student_check_answer"),
            recommended_repair_strategy="review_concept_and_example",
        )
    )

    plan, repair_text, executed_tools = await run_repair_misconception(
        check_eval=eval_obj,
        context=context,
        target_concept=state.get("check_question", {}).get(
            "target_concept", "khái niệm"
        ),
        retry_count=retry,
        model=llm,
    )

    trace = list(state.get("tool_trace", []))
    for t_name in executed_tools:
        trace.append(
            {
                "tool": t_name,
                "status": "success",
                "prompt_version": "1.0.0",
                "model": get_settings().OPENAI_MODEL,
                "details": {"repair_step": True},
            }
        )

    return {
        "repair_plan": plan.model_dump(),
        "grounded_answer": repair_text,
        "check_question": None,
        "student_check_answer": None,
        "check_result": None,
        "retry_count": retry + 1,
        "tool_trace": trace,
        "status": "running",
    }


async def safe_end_node(state: LearningLoopState) -> dict[str, Any]:
    """Node 9: Terminal node reached when max retry count is reached."""
    msg = (
        "Bạn đã nỗ lực trả lời các câu hỏi kiểm tra! Khái niệm này tương đối phức tạp. "
        "Bạn nên đọc lại tài liệu bài học hoặc trao đổi với giảng viên để nắm vững hơn nhé."
    )
    return {
        "grounded_answer": msg,
        "status": "running",
    }


async def suggest_followups_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 10: Generate follow-up suggestions."""
    query = state.get("user_query", "")
    context = state.get("selected_context", "")
    grounded_ans = state.get("grounded_answer", "")
    llm = model or get_fast_model()

    sug = await run_suggest_followups(query, context, grounded_ans, llm)
    f_list = [f.model_dump() for f in sug.followups]

    return {
        "followups": f_list,
        "status": "running",
        "tool_trace": _record_trace(state, "suggest_followups", "success"),
    }


async def output_guard_node(state: LearningLoopState) -> dict[str, Any]:
    """Node 11: Output guard sanitizing final assistant message."""
    ans = state.get("grounded_answer", "")
    sanitized, _leak = sanitize_output(ans)

    (
        clean_msg,
        clean_clar,
        clean_check,
        clean_followups,
        clean_citations,
        clean_blocked,
    ) = sanitize_all_output_fields(
        assistant_message=sanitized,
        clarification_question=state.get("clarification_question"),
        check_question=state.get("check_question"),
        followups=state.get("followups", []),
        citations=state.get("citations", []),
        blocked_reason=state.get("blocked_reason"),
    )

    curr_status = state.get("status", "completed")
    final_status = (
        curr_status
        if curr_status in ("awaiting_clarification", "awaiting_check", "blocked")
        else "completed"
    )

    return {
        "grounded_answer": clean_msg or "",
        "clarification_question": clean_clar,
        "check_question": clean_check,
        "followups": clean_followups,
        "citations": clean_citations,
        "blocked_reason": clean_blocked,
        "status": final_status,
    }
