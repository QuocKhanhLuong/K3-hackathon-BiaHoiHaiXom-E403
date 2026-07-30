"""LangGraph StateGraph builder and compiler."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from vlearn_ai.graph.nodes import (
    ask_clarification_node,
    check_understanding_node,
    context_guard_node,
    grounded_answer_node,
    grounding_guard_node,
    input_guard_node,
    misconception_node,
    output_guard_node,
    router_node,
    suggest_followups_node,
)
from vlearn_ai.graph.routes import (
    route_after_ask_clarification,
    route_after_check_eval,
    route_after_grounding_guard,
    route_after_input_guard,
    route_after_router,
)
from vlearn_ai.graph.state import LearningLoopState


def build_learning_graph(
    model: BaseChatModel | None = None,
    checkpointer: Any | None = None,
):
    """Build and compile the LangGraph StateGraph for VLearn Learning Loop."""
    graph = StateGraph(LearningLoopState)

    # Node wrappers passing optional model override
    async def n_input_guard(state: LearningLoopState):
        return await input_guard_node(state, model=model)

    async def n_router(state: LearningLoopState):
        return await router_node(state, model=model)

    async def n_ask_clarification(state: LearningLoopState):
        return await ask_clarification_node(state, model=model)

    async def n_grounded_answer(state: LearningLoopState):
        return await grounded_answer_node(state, model=model)

    async def n_check_understanding(state: LearningLoopState):
        return await check_understanding_node(state, model=model)

    async def n_misconception(state: LearningLoopState):
        return await misconception_node(state, model=model)

    async def n_suggest_followups(state: LearningLoopState):
        return await suggest_followups_node(state, model=model)

    # Add nodes
    graph.add_node("input_guard", n_input_guard)
    graph.add_node("context_guard", context_guard_node)
    graph.add_node("router", n_router)
    graph.add_node("ask_clarification", n_ask_clarification)
    graph.add_node("grounded_answer", n_grounded_answer)
    graph.add_node("grounding_guard", grounding_guard_node)
    graph.add_node("check_understanding", n_check_understanding)
    graph.add_node("misconception", n_misconception)
    graph.add_node("suggest_followups", n_suggest_followups)
    graph.add_node("output_guard", output_guard_node)

    # Add edges
    graph.add_edge(START, "input_guard")

    graph.add_conditional_edges(
        "input_guard",
        route_after_input_guard,
        {
            "context_guard": "context_guard",
            "end": END,
        },
    )

    graph.add_edge("context_guard", "router")

    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "simple": "grounded_answer",
            "clarify": "ask_clarification",
            "check": "grounded_answer",
            "deep": "suggest_followups",
        },
    )

    graph.add_conditional_edges(
        "ask_clarification",
        route_after_ask_clarification,
        {
            "grounded_answer": "grounded_answer",
            "end": END,
        },
    )

    graph.add_edge("grounded_answer", "grounding_guard")

    graph.add_conditional_edges(
        "grounding_guard",
        route_after_grounding_guard,
        {
            "output_guard": "output_guard",
            "check_understanding": "check_understanding",
        },
    )

    graph.add_conditional_edges(
        "check_understanding",
        route_after_check_eval,
        {
            "suggest_followups": "suggest_followups",
            "misconception": "misconception",
            "output_guard": "output_guard",
            "end": END,
        },
    )

    graph.add_edge("misconception", "check_understanding")
    graph.add_edge("suggest_followups", "output_guard")
    graph.add_edge("output_guard", END)

    cp = checkpointer if checkpointer is not None else MemorySaver()
    return graph.compile(checkpointer=cp)
