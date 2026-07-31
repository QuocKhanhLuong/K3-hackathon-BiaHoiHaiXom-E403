"""LangGraph workflow node implementations with pure native interrupt() and strict error handling."""

import asyncio
import re
import threading
import time
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.types import interrupt

from vlearn_ai.config import get_settings
from vlearn_ai.graph.state import LearningLoopState
from vlearn_ai.guardrails.context_guard import check_context_safety
from vlearn_ai.guardrails.grounding_guard import normalize_citations, validate_grounding
from vlearn_ai.guardrails.input_guard import assess_input_injection
from vlearn_ai.guardrails.output_guard import (
    sanitize_all_output_fields,
    sanitize_output,
    sanitize_tool_trace,
)
from vlearn_ai.model import get_fast_model, get_generation_model
from vlearn_ai.prompts.grounding_repair import GROUNDING_REPAIR_PROMPT_VERSION
from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.prompts.pedagogical_tools import (
    GIVE_DIRECT_ANSWER_PROMPT_VERSION,
    GIVE_EXAMPLE_PROMPT_VERSION,
    GIVE_HINT_PROMPT_VERSION,
    MOTIVATE_PROMPT_VERSION,
    REVIEW_CONCEPT_PROMPT_VERSION,
)
from vlearn_ai.prompts.repair import REPAIR_PROMPT_VERSION
from vlearn_ai.prompts.router import ROUTER_SYSTEM_PROMPT, ROUTER_USER_PROMPT_TEMPLATE
from vlearn_ai.schemas import (
    AICoreBaseError,
    CheckEvaluation,
    CheckOption,
    Citation,
    GroundedClaim,
    MicroCheck,
    RouteOutput,
)
from vlearn_ai.tools.give_direct_answer import execute_give_direct_answer
from vlearn_ai.tools.repair_grounded_answer import execute_repair_grounded_answer
from vlearn_ai.tools.review_concept import execute_review_concept
from vlearn_ai.workflows.ask_clarification import run_ask_clarification
from vlearn_ai.workflows.check_understanding import run_check_understanding
from vlearn_ai.workflows.detect_misconception import run_detect_misconception
from vlearn_ai.workflows.repair_misconception import run_repair_misconception
from vlearn_ai.workflows.suggest_followups import run_suggest_followups


def _get_model_name(model: BaseChatModel | None) -> str:
    """Extract model name from injected model or settings."""
    if model and hasattr(model, "model_name"):
        return str(model.model_name)
    if model and hasattr(model, "model"):
        return str(model.model)
    return get_settings().OPENAI_MODEL


def _record_trace(
    state: LearningLoopState,
    tool: str,
    status: str = "success",
    details: dict | None = None,
    model: BaseChatModel | None = None,
    prompt_version: str = "1.0.0",
    latency_ms: int | None = None,
) -> list[dict]:
    trace = list(state.get("tool_trace", []))
    entry: dict[str, Any] = {
        "tool": tool,
        "status": status,
        "prompt_version": prompt_version,
        "model": _get_model_name(model),
    }
    if latency_ms is not None:
        entry["latency_ms"] = latency_ms
    if details:
        entry["details"] = details
    trace.append(entry)
    return trace


def _run_async(coro):
    """Run an async helper from sync code, including when an event loop is already active."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    outcome: dict[str, Any] = {}
    error: list[BaseException] = []

    def runner() -> None:
        try:
            outcome["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 - background thread bridge
            error.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return outcome["value"]


def _safe_node(node_name: str):
    """Decorator that converts exceptions into failure state updates."""

    def decorator(func):
        def wrapper(state: LearningLoopState, model: BaseChatModel | None = None):
            try:
                return func(state, model)
            except AICoreBaseError as exc:
                return {
                    "status": "failed",
                    "failure_code": type(exc).__name__,
                    "failure_stage": node_name,
                    "tool_trace": _record_trace(
                        state, node_name, "failed", {"error": type(exc).__name__}, model
                    ),
                }
            except Exception as exc:  # noqa: BLE001 - node safety boundary
                return {
                    "status": "failed",
                    "failure_code": type(exc).__name__,
                    "failure_stage": node_name,
                    "tool_trace": _record_trace(
                        state, node_name, "failed", {"error": type(exc).__name__}, model
                    ),
                }

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator


# =====================================================================
# Node 1: Input Guard
# =====================================================================
@_safe_node("input_guard")
def input_guard_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Input guard checking initial query for prompt injection attacks."""
    query = state.get("user_query", "")
    llm = model or get_fast_model()
    t0 = time.time()

    assessment = _run_async(assess_input_injection(query, llm))
    ms = int((time.time() - t0) * 1000)

    if assessment.injection_detected:
        return {
            "status": "blocked",
            "blocked_reason": f"Prompt injection blocked: {assessment.reason}",
            "tool_trace": _record_trace(
                state,
                "input_guard",
                "blocked",
                {"reason": assessment.reason},
                llm,
                latency_ms=ms,
            ),
        }
    return {"status": "running"}


# =====================================================================
# Node 2: Context Guard
# =====================================================================
def context_guard_node(state: LearningLoopState) -> dict[str, Any]:
    """Context guard verifying course context length and safety."""
    context = state.get("selected_context", "")
    cfg = get_settings()

    res = check_context_safety(context, max_chars=cfg.AI_CONTEXT_MAX_CHARS)
    if res["context_injection_detected"]:
        return {
            "selected_context": res["context"],
            "context_truncated": res["context_truncated"],
            "context_injection_detected": True,
            "context_injection_patterns": res["context_injection_patterns"],
            "status": "blocked",
            "blocked_reason": "Prompt injection detected in selected course context.",
            "tool_trace": _record_trace(
                state,
                "context_guard",
                "blocked",
                {"context_injection_detected": True},
            ),
        }
    return {
        "selected_context": res["context"],
        "context_truncated": res["context_truncated"],
        "context_injection_detected": res["context_injection_detected"],
        "context_injection_patterns": res["context_injection_patterns"],
        "status": "running",
        "tool_trace": _record_trace(
            state,
            "context_guard",
            "success",
            {"context_injection_detected": res["context_injection_detected"]},
        ),
    }


# =====================================================================
# Node 3: Router
# =====================================================================
@_safe_node("router")
def router_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Router node classifying query into 1 of 4 routes."""
    query = state.get("user_query", "")
    context = state.get("selected_context", "")
    llm = model or get_fast_model()
    t0 = time.time()

    untrusted_payload = ROUTER_USER_PROMPT_TEMPLATE.format(
        selected_context=context, user_query=query
    )
    messages = build_trusted_messages(ROUTER_SYSTEM_PROMPT, untrusted_payload)

    route_out: RouteOutput | None = None
    route_src = "structured_model"
    try:
        if hasattr(llm, "with_structured_output"):
            structured = llm.with_structured_output(RouteOutput)
            res = _run_async(structured.ainvoke(messages))
            if isinstance(res, RouteOutput):
                route_out = res
    except (AttributeError, ValueError, TypeError, KeyError):
        route_out = None

    if route_out is None:
        route_src = "deterministic_fallback"
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

    ms = int((time.time() - t0) * 1000)
    return {
        "route": route_out.route,
        "route_confidence": route_out.confidence,
        "route_reason": route_out.reason,
        "route_source": route_src,
        "tool_trace": _record_trace(
            state,
            "router",
            "success",
            {
                "route": route_out.route,
                "route_source": route_src,
                "reason": route_out.reason,
            },
            llm,
            latency_ms=ms,
        ),
    }


# =====================================================================
# Node 4A: Generate Clarification
# =====================================================================
@_safe_node("generate_clarification")
def generate_clarification_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Generate clarification question (no interrupt)."""
    query = state.get("user_query", "")
    context = state.get("selected_context", "")
    llm = model or get_fast_model()

    req = _run_async(run_ask_clarification(query, context, llm))
    return {
        "clarification_question": req.clarification_question,
        "status": "awaiting_clarification",
        "tool_trace": _record_trace(state, "ask_clarification", "success", model=llm),
    }


# =====================================================================
# Node 4B: Await Clarification (pure interrupt)
# =====================================================================
def await_clarification_node(state: LearningLoopState) -> dict[str, Any]:
    """Pure native interrupt pausing graph for clarification answer."""
    question = state.get("clarification_question")

    resumed_input = interrupt(
        {
            "type": "clarification_request",
            "question": question,
        }
    )

    return {
        "clarification_answer": str(resumed_input),
        "status": "running",
    }


# =====================================================================
# Node 4C: Guard Clarification Input
# =====================================================================
@_safe_node("guard_clarification_input")
def guard_clarification_input_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Guard prompt injection on resumed clarification answer."""
    clar_ans = state.get("clarification_answer", "")
    llm = model or get_fast_model()

    assessment = _run_async(assess_input_injection(clar_ans, llm))
    if assessment.injection_detected:
        return {
            "status": "blocked",
            "blocked_reason": f"Prompt injection in clarification answer: {assessment.reason}",
            "tool_trace": _record_trace(
                state,
                "input_guard",
                "blocked",
                {"reason": assessment.reason},
                llm,
            ),
        }
    return {"status": "running"}


# =====================================================================
# Node 5: Grounded Answer
# =====================================================================
@_safe_node("grounded_answer")
def grounded_answer_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Produce grounded answer using direct answer or review concept tool."""
    query = state.get("user_query", "")
    if state.get("clarification_answer"):
        query = f"{query} (Làm rõ: {state.get('clarification_answer')})"

    context = state.get("selected_context", "")
    route = state.get("route", "simple")
    llm = model or get_generation_model()
    trace = list(state.get("tool_trace", []))

    if route == "simple":
        ans_obj = _run_async(execute_give_direct_answer(query, context, llm))
        tool_used = "give_direct_answer"
    else:
        ans_obj = _run_async(execute_review_concept(query, context, llm))
        tool_used = "review_concept"

    prompt_version = (
        GIVE_DIRECT_ANSWER_PROMPT_VERSION
        if tool_used == "give_direct_answer"
        else REVIEW_CONCEPT_PROMPT_VERSION
    )
    trace = _record_trace(
        state, tool_used, "success", model=llm, prompt_version=prompt_version
    )
    citations_list = [c.model_dump() for c in ans_obj.citations]
    claims_list = [cl.model_dump() for cl in ans_obj.claims]

    return {
        "grounded_answer": ans_obj.answer,
        "grounded_claims": claims_list,
        "citations": citations_list,
        "candidate_answer": ans_obj.answer,
        "candidate_claims": claims_list,
        "candidate_citations": citations_list,
        "answerability": ans_obj.answerability,
        "answerability_code": ans_obj.answerability_code,
        "tool_trace": trace,
    }


# =====================================================================
# Node 6: Grounding Guard
# =====================================================================
def grounding_guard_node(state: LearningLoopState) -> dict[str, Any]:
    """Grounding guard verifying citations against context."""
    answer = state.get("grounded_answer", "")
    citations_data = state.get("citations", [])
    context = state.get("selected_context", "")
    claims_data = state.get("grounded_claims", [])
    if state.get("answerability") == "insufficient_context":
        if citations_data or claims_data:
            return {
                "grounding_valid": False,
                "grounding_error": "insufficient_context must not include claims or citations.",
                "grounding_failure_type": "invalid_insufficient_context",
                "grounding_invalid_citation_ids": [],
                "grounding_conflicting_citation_ids": [],
                "grounding_uncovered_sentences": [],
                "status": "running",
                "tool_trace": _record_trace(state, "grounding_guard", "failed"),
            }
        return {
            "grounding_valid": True,
            "grounding_error": None,
            "grounding_failure_type": None,
            "grounding_invalid_citation_ids": [],
            "grounding_conflicting_citation_ids": [],
            "grounding_uncovered_sentences": [],
            "status": "running",
            "tool_trace": _record_trace(state, "grounding_guard", "success"),
        }

    try:
        citations = [Citation(**c) for c in citations_data if isinstance(c, dict)]
        claims = [GroundedClaim(**c) for c in claims_data if isinstance(c, dict)]
    except Exception as exc:  # noqa: BLE001 - validation boundary for model output
        return {
            "grounding_valid": False,
            "grounding_error": f"Invalid grounded structure: {exc}",
            "grounding_failure_type": "invalid_grounded_structure",
            "grounding_invalid_citation_ids": [],
            "grounding_conflicting_citation_ids": [],
            "grounding_uncovered_sentences": [],
            "status": "running",
            "tool_trace": _record_trace(
                state,
                "grounding_guard",
                "failed",
                {"error": type(exc).__name__},
            ),
        }

    normalization = normalize_citations(citations)
    result = validate_grounding(answer, citations, context, claims=claims)

    return {
        "citations": [citation.model_dump() for citation in normalization.citations],
        "grounding_valid": result.valid,
        "grounding_error": result.error,
        "grounding_failure_type": result.failure_type,
        "grounding_invalid_citation_ids": result.invalid_citation_ids,
        "grounding_conflicting_citation_ids": result.conflicting_citation_ids,
        "grounding_uncovered_sentences": result.uncovered_sentences,
        "status": "running",
        "tool_trace": _record_trace(
            state, "grounding_guard", "success" if result.valid else "failed"
        ),
    }


# =====================================================================
# Node 6B: Grounding Failure
# =====================================================================
def grounding_failure_node(state: LearningLoopState) -> dict[str, Any]:
    """Explicit grounding failure abstention node."""
    msg = (
        "Ngữ cảnh bài học hiện tại chưa đủ để tạo câu trả lời có căn cứ. "
        "Bạn hãy chọn thêm nội dung liên quan hoặc làm rõ câu hỏi."
    )
    return {
        "grounded_answer": msg,
        "abstention_message": msg,
        "grounding_failure_type": state.get("grounding_failure_type"),
        "answerability": "insufficient_context",
        "answerability_code": "grounding_unavailable",
        "citations": [],
        "grounded_claims": [],
        "status": "failed",
        "tool_trace": _record_trace(
            state,
            "grounding_failure",
            "failed",
            {"reason": state.get("grounding_error")},
        ),
    }


@_safe_node("grounding_repair")
def grounding_repair_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Attempt exactly one structured repair after factual grounding failure."""
    llm = model or get_generation_model()
    started = time.time()
    repaired = _run_async(
        execute_repair_grounded_answer(
            candidate_answer=state.get("candidate_answer"),
            candidate_claims=list(state.get("candidate_claims", [])),
            candidate_citations=list(state.get("candidate_citations", [])),
            grounding_error=state.get("grounding_error"),
            grounding_failure_type=state.get("grounding_failure_type"),
            grounding_invalid_citation_ids=list(
                state.get("grounding_invalid_citation_ids", [])
            ),
            grounding_conflicting_citation_ids=list(
                state.get("grounding_conflicting_citation_ids", [])
            ),
            grounding_uncovered_sentences=list(
                state.get("grounding_uncovered_sentences", [])
            ),
            user_query=state.get("user_query", ""),
            context=state.get("selected_context", ""),
            model=llm,
        )
    )
    citations = [citation.model_dump() for citation in repaired.citations]
    claims = [claim.model_dump() for claim in repaired.claims]
    retry_count = state.get("grounding_retry_count", 0) + 1
    return {
        "grounded_answer": repaired.answer,
        "grounded_claims": claims,
        "citations": citations,
        "candidate_answer": repaired.answer,
        "candidate_claims": claims,
        "candidate_citations": citations,
        "answerability": repaired.answerability,
        "answerability_code": repaired.answerability_code,
        "grounding_retry_count": retry_count,
        "tool_trace": _record_trace(
            state,
            "grounding_repair",
            "success",
            {
                "failure_type": state.get("grounding_failure_type"),
                "retry_count": retry_count,
            },
            llm,
            prompt_version=GROUNDING_REPAIR_PROMPT_VERSION,
            latency_ms=int((time.time() - started) * 1000),
        ),
    }


# =====================================================================
# Node 7A: Generate Check
# =====================================================================
@_safe_node("generate_check")
def generate_check_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Generate understanding check question (no interrupt)."""
    context = state.get("selected_context", "")
    grounded_ans = state.get("grounded_answer", "")
    llm = model or get_generation_model()

    prev_check = (
        MicroCheck(**state["check_question"]) if state.get("check_question") else None
    )
    micro_check = _run_async(
        run_check_understanding(context, grounded_ans, llm, previous_check=prev_check)
    )

    return {
        "check_question": micro_check.model_dump(),
        "student_check_answer": None,
        "check_result": None,
        "status": "awaiting_check",
        "tool_trace": _record_trace(
            state, "validate_understanding", "success", model=llm
        ),
    }


# =====================================================================
# Node 7B: Await Check (pure interrupt)
# =====================================================================
def await_check_node(state: LearningLoopState) -> dict[str, Any]:
    """Pure native interrupt pausing graph for student check answer."""
    check = state.get("check_question") or {}

    resumed_answer = interrupt(
        {
            "type": check.get("question_type", "multiple_choice"),
            "question": check.get("question"),
            "options": check.get("options", []),
        }
    )

    return {
        "student_check_answer": str(resumed_answer),
        "status": "running",
    }


# =====================================================================
# Node 7C: Guard Check Input
# =====================================================================
@_safe_node("guard_check_input")
def guard_check_input_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Guard prompt injection on resumed student check answer."""
    student_ans = state.get("student_check_answer", "")
    llm = model or get_fast_model()

    assessment = _run_async(assess_input_injection(student_ans, llm))
    if assessment.injection_detected:
        return {
            "status": "blocked",
            "blocked_reason": f"Prompt injection in check answer: {assessment.reason}",
            "tool_trace": _record_trace(
                state,
                "input_guard",
                "blocked",
                {"reason": assessment.reason},
                llm,
            ),
        }
    return {"status": "running"}


# =====================================================================
# Node 7D: Evaluate Check
# =====================================================================
@_safe_node("evaluate_check")
def evaluate_check_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Evaluate resumed student check answer against question."""
    context = state.get("selected_context", "")
    check_q = state.get("check_question") or {}
    student_ans = state.get("student_check_answer", "")
    llm = model or get_generation_model()

    raw_options = check_q.get("options") or []
    typed_options = [CheckOption(**opt) for opt in raw_options if isinstance(opt, dict)]

    eval_res = _run_async(
        run_detect_misconception(
            question=check_q.get("question", ""),
            expected_answer=check_q.get("expected_answer", ""),
            student_answer=student_ans,
            context=context,
            correct_option_id=check_q.get("correct_option_id"),
            options=typed_options,
            model=llm,
        )
    )

    grounded_msg = (
        eval_res.error_explanation
        if eval_res.is_correct
        else state.get("grounded_answer", "")
    )
    return {
        "check_result": eval_res.model_dump(),
        "grounded_answer": grounded_msg,
        "status": "running",
        "tool_trace": _record_trace(state, "evaluate_check", "success", model=llm),
    }


# =====================================================================
# Node 8: Misconception Repair
# =====================================================================
@_safe_node("misconception")
def misconception_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Detect misconception and execute repair plan."""
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

    repair_execution = _run_async(
        run_repair_misconception(
            check_eval=eval_obj,
            context=context,
            target_concept=state.get("check_question", {}).get(
                "target_concept", "khái niệm"
            ),
            retry_count=retry,
            model=llm,
        )
    )

    trace = list(state.get("tool_trace", []))
    trace.append(
        {
            "tool": "repair_misconception",
            "status": "success",
            "prompt_version": REPAIR_PROMPT_VERSION,
            "model": _get_model_name(llm),
            "details": {"repair_planner": True},
        }
    )
    prompt_versions = {
        "review_concept": REVIEW_CONCEPT_PROMPT_VERSION,
        "give_example": GIVE_EXAMPLE_PROMPT_VERSION,
        "give_hint": GIVE_HINT_PROMPT_VERSION,
        "motivate": MOTIVATE_PROMPT_VERSION,
    }
    for t_name in repair_execution.executed_tools:
        trace.append(
            {
                "tool": t_name,
                "status": "success",
                "prompt_version": prompt_versions[t_name],
                "model": _get_model_name(llm),
                "details": {"repair_step": True},
            }
        )

    return {
        "repair_plan": repair_execution.plan.model_dump(),
        "grounded_answer": repair_execution.grounded_repair.answer,
        "grounded_claims": [
            claim.model_dump() for claim in repair_execution.grounded_repair.claims
        ],
        "citations": [
            citation.model_dump()
            for citation in repair_execution.grounded_repair.citations
        ],
        "supplemental_actions": repair_execution.supplemental_actions.model_dump(),
        "retry_count": retry + 1,
        "tool_trace": trace,
        "status": "running",
    }


# =====================================================================
# Node 9: Safe End
# =====================================================================
def safe_end_node(state: LearningLoopState) -> dict[str, Any]:
    """Terminal node reached when max retry count is reached."""
    msg = (
        "Bạn đã nỗ lực trả lời các câu hỏi kiểm tra! Khái niệm này tương đối phức tạp. "
        "Bạn nên đọc lại tài liệu bài học hoặc trao đổi với giảng viên để nắm vững hơn nhé."
    )
    return {
        "grounded_answer": msg,
        "status": "completed",
    }


# =====================================================================
# Node 10: Suggest Follow-ups
def _generate_insufficient_context_followups(
    state: LearningLoopState,
) -> list[dict[str, str]]:
    """Generate 2-3 deterministic clarification/next-step suggestions for insufficient context without LLM invocation."""
    query = (state.get("user_query") or "").strip()
    clean_topic = query
    for prefix in [
        "cho tôi biết",
        "giải thích",
        "nói về",
        "khái niệm",
        "là gì",
        "thế nào",
        "tìm hiểu về",
        "trình bày",
        "chi tiết về",
        "so sánh",
        "hỏi về",
    ]:
        if clean_topic.lower().startswith(prefix):
            clean_topic = clean_topic[len(prefix) :].strip()
            break
    clean_topic = re.sub(r"[?.,!]", "", clean_topic).strip()
    topic_display = clean_topic[:30] if clean_topic else "khái niệm này"

    return [
        {
            "label": f"Làm rõ câu hỏi về '{topic_display}'",
            "question": f"Bạn có thể làm rõ hơn khía cạnh nào của '{topic_display}' mà bạn muốn tìm hiểu không?",
        },
        {
            "label": "Tra cứu toàn bộ bài học",
            "question": f"Nội dung về '{topic_display}' xuất hiện ở những slide hay chương nào trong khóa học?",
        },
        {
            "label": "Mối liên hệ bài học",
            "question": f"Khái niệm '{topic_display}' liên quan như thế nào đến nội dung bài học hiện tại?",
        },
    ]


def _generate_fallback_answerable_followups(
    state: LearningLoopState,
) -> list[dict[str, str]]:
    """Generate 2-3 fallback follow-up questions if LLM generation fails or returns empty."""
    query = (state.get("user_query") or "").strip()
    clean_topic = query
    for prefix in [
        "cho tôi biết",
        "giải thích",
        "nói về",
        "khái niệm",
        "là gì",
        "thế nào",
        "tìm hiểu về",
        "trình bày",
        "chi tiết về",
        "so sánh",
        "hỏi về",
    ]:
        if clean_topic.lower().startswith(prefix):
            clean_topic = clean_topic[len(prefix) :].strip()
            break
    clean_topic = re.sub(r"[?.,!]", "", clean_topic).strip()
    topic_display = clean_topic[:30] if clean_topic else "chủ đề này"

    return [
        {
            "label": "Ví dụ thực tế",
            "question": f"Cho tôi xin ví dụ minh họa thực tế về '{topic_display}'?",
        },
        {
            "label": "Điểm cần lưu ý",
            "question": f"Những điểm quan trọng cần lưu ý khi ứng dụng '{topic_display}' là gì?",
        },
        {
            "label": "Đào sâu hơn",
            "question": f"Bạn có thể giải thích chi tiết hơn về các thành phần cốt lõi của '{topic_display}' không?",
        },
    ]


# =====================================================================
# Node 10: Suggest Follow-ups
# =====================================================================
@_safe_node("suggest_followups")
def suggest_followups_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    """Generate follow-up suggestions."""
    if state.get("answerability") == "insufficient_context":
        f_list = _generate_insufficient_context_followups(state)
        return {
            "followups": f_list,
            "status": "running",
            "tool_trace": _record_trace(
                state, "suggest_followups", "success", model=model
            ),
        }

    query = state.get("user_query", "")
    context = state.get("selected_context", "")
    grounded_ans = state.get("grounded_answer", "")
    llm = model or get_fast_model()

    f_list = []
    try:
        sug = _run_async(run_suggest_followups(query, context, grounded_ans, llm))
        f_list = [f.model_dump() for f in sug.followups]
    except Exception:  # noqa: BLE001 - optional follow-up enhancement
        f_list = []

    if not f_list or len(f_list) < 2:
        f_list = _generate_fallback_answerable_followups(state)

    return {
        "followups": f_list,
        "status": "running",
        "tool_trace": _record_trace(state, "suggest_followups", "success", model=llm),
    }


# =====================================================================
# Node 11: Failure
# =====================================================================
def failure_node(state: LearningLoopState) -> dict[str, Any]:
    """Safe failure node for unhandled exceptions or execution failures."""
    msg = (
        "Hệ thống chưa thể tạo phản hồi ổn định cho lượt này. "
        "Bạn hãy thử lại hoặc chọn lại nội dung bài học."
    )
    return {
        "grounded_answer": msg,
        "status": "failed",
        "failure_code": state.get("failure_code", "INTERNAL_EXECUTION_ERROR"),
        "failure_stage": state.get("failure_stage", "workflow"),
        "tool_trace": _record_trace(state, "failure_node", "failed"),
    }


# =====================================================================
# Node 12: Output Guard
# =====================================================================
def output_guard_node(state: LearningLoopState) -> dict[str, Any]:
    """Output guard sanitizing final assistant message."""
    ans = state.get("grounded_answer", "")
    sanitized, _leak = sanitize_output(ans)

    curr_status = state.get("status", "running")
    raw_followups = state.get("followups", [])
    if curr_status in ("blocked", "failed", "awaiting_clarification", "awaiting_check"):
        final_status = curr_status
        raw_followups = []
    else:
        final_status = "completed"

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
        followups=raw_followups,
        citations=state.get("citations", []),
        blocked_reason=state.get("blocked_reason"),
    )

    clean_trace = sanitize_tool_trace(state.get("tool_trace", []))

    return {
        "grounded_answer": clean_msg or "",
        "clarification_question": clean_clar,
        "check_question": clean_check,
        "followups": clean_followups,
        "citations": clean_citations,
        "blocked_reason": clean_blocked,
        "status": final_status,
        "tool_trace": clean_trace,
    }
