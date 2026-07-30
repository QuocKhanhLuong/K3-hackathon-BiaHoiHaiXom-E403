"""LangGraph StateGraph builder for VLearn AI Core Orchestration Engine."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from vlearn_ai.graph.nodes import (
    await_check_node,
    await_clarification_node,
    context_guard_node,
    evaluate_check_node,
    failure_node,
    generate_check_node,
    generate_clarification_node,
    grounded_answer_node,
    grounding_failure_node,
    grounding_guard_node,
    grounding_repair_node,
    guard_check_input_node,
    guard_clarification_input_node,
    input_guard_node,
    misconception_node,
    output_guard_node,
    router_node,
    safe_end_node,
    suggest_followups_node,
)
from vlearn_ai.graph.routes import (
    route_after_await_check,
    route_after_await_clarification,
    route_after_check_eval,
    route_after_context_guard,
    route_after_grounding_guard,
    route_after_guard_check_input,
    route_after_guard_clarification_input,
    route_after_input_guard,
    route_after_misconception,
    route_after_router,
)
from vlearn_ai.graph.state import LearningLoopState


def _route_or_failure(route_fn):
    def _wrapped(state: LearningLoopState):
        if state.get("status") == "failed":
            return "failure"
        return route_fn(state)

    return _wrapped


def build_learning_loop_graph(
    model: BaseChatModel | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """Build compiled StateGraph for Learning Loop orchestration."""
    builder = StateGraph(LearningLoopState)

    # Node wrappers passing optional model override
    def n_input_guard(state: LearningLoopState):
        return input_guard_node(state, model=model)

    def n_context_guard(state: LearningLoopState):
        return context_guard_node(state)

    def n_router(state: LearningLoopState):
        return router_node(state, model=model)

    def n_generate_clarification(state: LearningLoopState):
        return generate_clarification_node(state, model=model)

    def n_await_clarification(state: LearningLoopState):
        return await_clarification_node(state)

    def n_guard_clarification_input(state: LearningLoopState):
        return guard_clarification_input_node(state, model=model)

    def n_grounded_answer(state: LearningLoopState):
        return grounded_answer_node(state, model=model)

    def n_grounding_guard(state: LearningLoopState):
        return grounding_guard_node(state)

    def n_grounding_failure(state: LearningLoopState):
        return grounding_failure_node(state)

    def n_grounding_repair(state: LearningLoopState):
        return grounding_repair_node(state, model=model)

    def n_generate_check(state: LearningLoopState):
        return generate_check_node(state, model=model)

    def n_await_check(state: LearningLoopState):
        return await_check_node(state)

    def n_guard_check_input(state: LearningLoopState):
        return guard_check_input_node(state, model=model)

    def n_evaluate_check(state: LearningLoopState):
        return evaluate_check_node(state, model=model)

    def n_misconception(state: LearningLoopState):
        return misconception_node(state, model=model)

    def n_safe_end(state: LearningLoopState):
        return safe_end_node(state)

    def n_suggest_followups(state: LearningLoopState):
        return suggest_followups_node(state, model=model)

    def n_failure(state: LearningLoopState):
        return failure_node(state)

    def n_output_guard(state: LearningLoopState):
        return output_guard_node(state)

    # Add Graph Nodes
    builder.add_node("input_guard", n_input_guard)
    builder.add_node("context_guard", n_context_guard)
    builder.add_node("router", n_router)
    builder.add_node("generate_clarification", n_generate_clarification)
    builder.add_node("await_clarification", n_await_clarification)
    builder.add_node("guard_clarification_input", n_guard_clarification_input)
    builder.add_node("grounded_answer", n_grounded_answer)
    builder.add_node("grounding_guard", n_grounding_guard)
    builder.add_node("grounding_failure", n_grounding_failure)
    builder.add_node("grounding_repair", n_grounding_repair)
    builder.add_node("generate_check", n_generate_check)
    builder.add_node("await_check", n_await_check)
    builder.add_node("guard_check_input", n_guard_check_input)
    builder.add_node("evaluate_check", n_evaluate_check)
    builder.add_node("misconception", n_misconception)
    builder.add_node("safe_end", n_safe_end)
    builder.add_node("suggest_followups", n_suggest_followups)
    builder.add_node("failure", n_failure)
    builder.add_node("output_guard", n_output_guard)

    # ───── Wire Edges ─────
    builder.add_edge(START, "input_guard")
    builder.add_conditional_edges(
        "input_guard",
        _route_or_failure(route_after_input_guard),
        {
            "context_guard": "context_guard",
            "output_guard": "output_guard",
            "failure": "failure",
        },
    )
    builder.add_conditional_edges(
        "context_guard",
        _route_or_failure(route_after_context_guard),
        {"router": "router", "output_guard": "output_guard", "failure": "failure"},
    )
    builder.add_conditional_edges(
        "router",
        _route_or_failure(route_after_router),
        {
            "generate_clarification": "generate_clarification",
            "grounded_answer": "grounded_answer",
            "failure": "failure",
        },
    )

    # Clarification path
    builder.add_conditional_edges(
        "generate_clarification",
        _route_or_failure(lambda state: "await_clarification"),
        {"await_clarification": "await_clarification", "failure": "failure"},
    )
    builder.add_conditional_edges(
        "await_clarification",
        _route_or_failure(route_after_await_clarification),
        {
            "guard_clarification_input": "guard_clarification_input",
            "output_guard": "output_guard",
            "failure": "failure",
        },
    )
    builder.add_conditional_edges(
        "guard_clarification_input",
        _route_or_failure(route_after_guard_clarification_input),
        {
            "grounded_answer": "grounded_answer",
            "output_guard": "output_guard",
            "failure": "failure",
        },
    )

    # Grounded answer → grounding guard
    builder.add_conditional_edges(
        "grounded_answer",
        _route_or_failure(lambda state: "grounding_guard"),
        {"grounding_guard": "grounding_guard", "failure": "failure"},
    )
    builder.add_conditional_edges(
        "grounding_guard",
        _route_or_failure(route_after_grounding_guard),
        {
            "output_guard": "output_guard",
            "suggest_followups": "suggest_followups",
            "generate_check": "generate_check",
            "grounding_repair": "grounding_repair",
            "grounding_failure": "grounding_failure",
            "failure": "failure",
        },
    )
    builder.add_conditional_edges(
        "grounding_repair",
        _route_or_failure(lambda state: "grounding_guard"),
        {"grounding_guard": "grounding_guard", "failure": "failure"},
    )
    builder.add_edge("grounding_failure", "output_guard")

    # Check path
    builder.add_conditional_edges(
        "generate_check",
        _route_or_failure(lambda state: "await_check"),
        {"await_check": "await_check", "failure": "failure"},
    )
    builder.add_conditional_edges(
        "await_check",
        _route_or_failure(route_after_await_check),
        {
            "guard_check_input": "guard_check_input",
            "output_guard": "output_guard",
            "failure": "failure",
        },
    )
    builder.add_conditional_edges(
        "guard_check_input",
        _route_or_failure(route_after_guard_check_input),
        {
            "evaluate_check": "evaluate_check",
            "output_guard": "output_guard",
            "failure": "failure",
        },
    )
    builder.add_conditional_edges(
        "evaluate_check",
        _route_or_failure(route_after_check_eval),
        {
            "suggest_followups": "suggest_followups",
            "misconception": "misconception",
            "safe_end": "safe_end",
            "failure": "failure",
        },
    )

    # Misconception → grounding_guard (for repair grounding verification)
    builder.add_conditional_edges(
        "misconception",
        _route_or_failure(route_after_misconception),
        {"grounding_guard": "grounding_guard", "failure": "failure"},
    )

    # Terminal edges
    builder.add_edge("safe_end", "output_guard")
    builder.add_edge("suggest_followups", "output_guard")
    builder.add_edge("failure", "output_guard")
    builder.add_edge("output_guard", END)

    cp = checkpointer if checkpointer is not None else MemorySaver()
    return builder.compile(checkpointer=cp)
