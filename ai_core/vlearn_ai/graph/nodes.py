"""LangGraph workflow node implementations."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.types import interrupt

from vlearn_ai.config import get_settings
from vlearn_ai.graph.state import LearningLoopState
from vlearn_ai.guardrails.context_guard import check_context_safety
from vlearn_ai.guardrails.grounding_guard import verify_grounding
from vlearn_ai.guardrails.input_guard import assess_input_injection
from vlearn_ai.guardrails.output_guard import sanitize_output
from vlearn_ai.model import get_chat_model
from vlearn_ai.prompts.router import ROUTER_SYSTEM_PROMPT, ROUTER_USER_PROMPT_TEMPLATE
from vlearn_ai.schemas import CheckEvaluation, Citation, RouteOutput
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


def _safe_interrupt(payload: dict) -> str | None:
    try:
        res = interrupt(payload)
        return str(res) if res is not None else None
    except (RuntimeError, AttributeError, ValueError, TypeError):
        return None


async def input_guard_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 1: Input guard checking query for prompt injection attacks."""
    query = state.get("user_query", "")
    llm = model or get_chat_model()

    assessment = await assess_input_injection(query, llm)
    if assessment.injection_detected:
        state["status"] = "blocked"
        return {
            "status": "blocked",
            "blocked_reason": f"Prompt injection blocked: {assessment.reason}",
            "tool_trace": _record_trace(
                state, "input_guard", "blocked", {"reason": assessment.reason}
            ),
        }

    state["status"] = "running"
    return {"status": "running"}


async def context_guard_node(state: LearningLoopState) -> dict[str, Any]:
    """Node 2: Context guard verifying course context length and safety."""
    context = state.get("selected_context", "")
    cfg = get_settings()

    res = check_context_safety(context, max_chars=cfg.AI_CONTEXT_MAX_CHARS)
    state["selected_context"] = res["context"]
    state["status"] = "running"
    return {
        "selected_context": res["context"],
        "status": "running",
    }


async def router_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 3: Router node classifying query into 1 of 4 routes."""
    query = state.get("user_query", "")
    context = state.get("selected_context", "")
    llm = model or get_chat_model()

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
    except (AttributeError, ValueError, TypeError, RuntimeError):
        pass

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

    state["route"] = route_out.route
    state["route_confidence"] = route_out.confidence
    state["route_reason"] = route_out.reason

    return {
        "route": route_out.route,
        "route_confidence": route_out.confidence,
        "route_reason": route_out.reason,
        "tool_trace": _record_trace(
            state, "router", "success", {"route": route_out.route}
        ),
    }


async def ask_clarification_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 4: Ask clarification and pause for learner answer if needed."""
    query = state.get("user_query", "")
    context = state.get("selected_context", "")
    llm = model or get_chat_model()

    req = await run_ask_clarification(query, context, llm)

    clar_ans = state.get("clarification_answer")
    if not clar_ans:
        int_res = _safe_interrupt(
            {
                "type": "clarification_request",
                "question": req.clarification_question,
                "reason": req.reason,
            }
        )
        clar_ans = int_res or state.get("clarification_answer")

    if not clar_ans:
        state["status"] = "awaiting_clarification"
        state["clarification_question"] = req.clarification_question
        return {
            "clarification_question": req.clarification_question,
            "status": "awaiting_clarification",
            "tool_trace": _record_trace(state, "ask_clarification", "awaiting"),
        }

    state["status"] = "running"
    state["clarification_answer"] = clar_ans
    state["clarification_question"] = req.clarification_question
    return {
        "clarification_question": req.clarification_question,
        "clarification_answer": clar_ans,
        "status": "running",
        "tool_trace": _record_trace(state, "ask_clarification", "success"),
    }


async def grounded_answer_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 5: Produce grounded answer using direct answer or review concept tool."""
    query = state.get("user_query", "")
    if state.get("clarification_answer"):
        query = f"{query} (Làm rõ: {state.get('clarification_answer')})"

    context = state.get("selected_context", "")
    route = state.get("route", "simple")
    llm = model or get_chat_model()

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
    state["grounded_answer"] = ans_obj.answer
    state["citations"] = citations_list

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
    _is_valid, _err = verify_grounding(
        answer, [c.snippet for c in citations], citations, context
    )

    state["status"] = "running"
    return {"status": "running"}


async def check_understanding_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 7: Generate micro-check, pause for student answer if needed, and evaluate."""
    context = state.get("selected_context", "")
    grounded_ans = state.get("grounded_answer", "")
    llm = model or get_chat_model()

    # Step A: Generate check question if not present
    check_q = state.get("check_question")
    if not check_q:
        micro_check = await run_check_understanding(context, grounded_ans, llm)
        check_q = micro_check.model_dump()

    state["check_question"] = check_q

    # Step B: Check for student check answer
    student_ans = state.get("student_check_answer")
    if not student_ans:
        int_res = _safe_interrupt(
            {
                "type": "micro_check",
                "question": check_q.get("question"),
                "options": check_q.get("options"),
                "question_type": check_q.get("question_type"),
            }
        )
        student_ans = int_res or state.get("student_check_answer")

    if not student_ans:
        state["status"] = "awaiting_check"
        state["check_result"] = None
        return {
            "check_question": check_q,
            "student_check_answer": None,
            "check_result": None,
            "status": "awaiting_check",
            "tool_trace": _record_trace(state, "validate_understanding", "awaiting"),
        }

    # Step C: Evaluate answer when student_ans is provided
    eval_res = await run_detect_misconception(
        question=check_q.get("question", ""),
        expected_answer=check_q.get("expected_answer", ""),
        student_answer=student_ans,
        context=context,
        model=llm,
    )

    eval_dict = eval_res.model_dump()
    state["student_check_answer"] = student_ans
    state["check_result"] = eval_dict
    state["status"] = "running"

    return {
        "check_question": check_q,
        "student_check_answer": student_ans,
        "check_result": eval_dict,
        "status": "running",
        "tool_trace": _record_trace(state, "validate_understanding", "success"),
    }


async def misconception_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 8: Detect misconception and execute repair plan."""
    context = state.get("selected_context", "")
    check_result_dict = state.get("check_result")
    retry = state.get("retry_count", 0)
    max_retry = get_settings().AI_MAX_RETRY_COUNT
    llm = model or get_chat_model()

    if retry >= max_retry:
        msg = (
            "Bạn đã nỗ lực trả lời các câu hỏi kiểm tra! Khái niệm này tương đối phức tạp. "
            "Bạn nên đọc lại tài liệu bài học hoặc trao đổi với giảng viên để nắm vững hơn nhé."
        )
        state["status"] = "completed"
        state["grounded_answer"] = msg
        return {
            "status": "completed",
            "grounded_answer": msg,
        }

    if not isinstance(check_result_dict, dict) or not check_result_dict:
        check_eval = CheckEvaluation(
            is_correct=False,
            score=0.0,
            misconception_code="concept_confusion",
            error_explanation="Học viên chưa hiểu rõ câu hỏi kiểm tra.",
            answer_evidence=state.get("student_check_answer"),
            recommended_repair_strategy="review_concept_and_example",
        )
    else:
        check_eval = CheckEvaluation(**check_result_dict)

    plan, repair_text = await run_repair_misconception(
        check_eval=check_eval,
        context=context,
        target_concept=state.get("check_question", {}).get(
            "target_concept", "khái niệm"
        ),
        model=llm,
    )

    state["repair_plan"] = plan.model_dump()
    state["grounded_answer"] = repair_text
    state["check_question"] = None
    state["student_check_answer"] = None
    state["check_result"] = None
    state["retry_count"] = retry + 1

    return {
        "repair_plan": plan.model_dump(),
        "grounded_answer": repair_text,
        "check_question": None,
        "student_check_answer": None,
        "check_result": None,
        "retry_count": retry + 1,
        "tool_trace": _record_trace(state, "repair_misconception", "success"),
    }


async def suggest_followups_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Node 9: Generate follow-up suggestions."""
    query = state.get("user_query", "")
    context = state.get("selected_context", "")
    grounded_ans = state.get("grounded_answer", "")
    llm = model or get_chat_model()

    sug = await run_suggest_followups(query, context, grounded_ans, llm)
    f_list = [f.model_dump() for f in sug.followups]
    state["followups"] = f_list

    return {
        "followups": f_list,
        "tool_trace": _record_trace(state, "suggest_followups", "success"),
    }


async def output_guard_node(state: LearningLoopState) -> dict[str, Any]:
    """Node 10: Output guard sanitizing final assistant message."""
    ans = state.get("grounded_answer", "")
    sanitized, _leak = sanitize_output(ans)

    state["grounded_answer"] = sanitized
    state["status"] = "completed"

    return {
        "grounded_answer": sanitized,
        "status": "completed",
    }
