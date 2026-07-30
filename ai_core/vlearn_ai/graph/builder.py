"""Graph construction and node wiring using LangGraph StateGraph."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from vlearn_ai.graph.nodes import (
    await_check_node,
    await_clarification_node,
    context_guard_node,
    evaluate_check_node,
    generate_check_node,
    generate_clarification_node,
    grounded_answer_node,
    grounding_guard_node,
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
    route_after_grounding_guard,
    route_after_guard_check_input,
    route_after_guard_clarification_input,
    route_after_input_guard,
    route_after_router,
)
from vlearn_ai.graph.state import LearningLoopState


def build_learning_graph(
    model: BaseChatModel | None = None,
    checkpointer: Any | None = None,
):
    """Build and compile VLearn Learning Loop StateGraph."""
    graph = StateGraph(LearningLoopState)

    # 1. Add graph nodes
    async def n_input_guard(state: LearningLoopState):
        return await input_guard_node(state, model=model)

    async def n_context_guard(state: LearningLoopState):
        return await context_guard_node(state)

    async def n_router(state: LearningLoopState):
        return await router_node(state, model=model)

    async def n_generate_clarification(state: LearningLoopState):
        return await generate_clarification_node(state, model=model)

    async def n_await_clarification(state: LearningLoopState):
        return await_clarification_node(state)

    async def n_guard_clarification_input(state: LearningLoopState):
        return await guard_clarification_input_node(state, model=model)

    async def n_grounded_answer(state: LearningLoopState):
        return await grounded_answer_node(state, model=model)

    async def n_grounding_guard(state: LearningLoopState):
        return await grounding_guard_node(state)

    async def n_generate_check(state: LearningLoopState):
        return await generate_check_node(state, model=model)

    async def n_await_check(state: LearningLoopState):
        return await_check_node(state)

    async def n_guard_check_input(state: LearningLoopState):
        return await guard_check_input_node(state, model=model)

    async def n_evaluate_check(state: LearningLoopState):
        return await evaluate_check_node(state, model=model)

    async def n_misconception(state: LearningLoopState):
        return await misconception_node(state, model=model)

    async def n_safe_end(state: LearningLoopState):
        return await safe_end_node(state)

    async def n_suggest_followups(state: LearningLoopState):
        return await suggest_followups_node(state, model=model)

    async def n_output_guard(state: LearningLoopState):
        return await output_guard_node(state)

    graph.add_node("input_guard", n_input_guard)
    graph.add_node("context_guard", n_context_guard)
    graph.add_node("router", n_router)

    graph.add_node("generate_clarification", n_generate_clarification)
    graph.add_node("await_clarification", n_await_clarification)
    graph.add_node("guard_clarification_input", n_guard_clarification_input)

    graph.add_node("grounded_answer", n_grounded_answer)
    graph.add_node("grounding_guard", n_grounding_guard)

    graph.add_node("generate_check", n_generate_check)
    graph.add_node("await_check", n_await_check)
    graph.add_node("guard_check_input", n_guard_check_input)
    graph.add_node("evaluate_check", n_evaluate_check)

    graph.add_node("misconception", n_misconception)
    graph.add_node("safe_end", n_safe_end)
    graph.add_node("suggest_followups", n_suggest_followups)
    graph.add_node("output_guard", n_output_guard)

    # 2. Add edges & conditional routing
    graph.add_edge(START, "input_guard")
    graph.add_conditional_edges(
        "input_guard",
        route_after_input_guard,
        {
            "context_guard": "context_guard",
            "output_guard": "output_guard",
        },
    )
    graph.add_edge("context_guard", "router")

    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "simple": "grounded_answer",
            "generate_clarification": "generate_clarification",
            "check": "grounded_answer",
            "deep": "grounded_answer",
        },
    )

    graph.add_edge("generate_clarification", "await_clarification")
    graph.add_conditional_edges(
        "await_clarification",
        route_after_await_clarification,
        {
            "guard_clarification_input": "guard_clarification_input",
            "output_guard": "output_guard",
        },
    )
    graph.add_conditional_edges(
        "guard_clarification_input",
        route_after_guard_clarification_input,
        {
            "grounded_answer": "grounded_answer",
            "output_guard": "output_guard",
        },
    )

    graph.add_edge("grounded_answer", "grounding_guard")
    graph.add_conditional_edges(
        "grounding_guard",
        route_after_grounding_guard,
        {
            "output_guard": "output_guard",
            "suggest_followups": "suggest_followups",
            "generate_check": "generate_check",
        },
    )

    graph.add_edge("generate_check", "await_check")
    graph.add_conditional_edges(
        "await_check",
        route_after_await_check,
        {
            "guard_check_input": "guard_check_input",
            "output_guard": "output_guard",
        },
    )
    graph.add_conditional_edges(
        "guard_check_input",
        route_after_guard_check_input,
        {
            "evaluate_check": "evaluate_check",
            "output_guard": "output_guard",
        },
    )

    graph.add_conditional_edges(
        "evaluate_check",
        route_after_check_eval,
        {
            "suggest_followups": "suggest_followups",
            "misconception": "misconception",
            "safe_end": "safe_end",
        },
    )

    graph.add_edge("misconception", "generate_check")
    graph.add_edge("safe_end", "output_guard")
    graph.add_edge("suggest_followups", "output_guard")
    graph.add_edge("output_guard", END)

    return graph.compile(checkpointer=checkpointer)
