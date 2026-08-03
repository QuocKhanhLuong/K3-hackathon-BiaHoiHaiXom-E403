import sys

# 1. Update router.py
router_path = "ai_core/vlearn_ai/prompts/router.py"
with open(router_path, "r", encoding="utf-8") as f:
    content = f.read()

if "out_of_context" not in content:
    content = content.replace(
        "4. `deep`: Câu hỏi chuyên sâu, yêu cầu phân tích kiến trúc, tại sao hoặc đào sâu nguyên lý.",
        "4. `deep`: Câu hỏi chuyên sâu, yêu cầu phân tích kiến trúc, tại sao hoặc đào sâu nguyên lý.\n5. `out_of_context`: Câu hỏi nằm ngoài tài liệu bài học nhưng VẪN thuôc lĩnh vực môn học (domain) và có thể trả lời bằng kiến thức chung."
    )
    content = content.replace(
        '"route": "simple" | "clarify" | "check" | "deep",',
        '"route": "simple" | "clarify" | "check" | "deep" | "out_of_context",'
    )
    with open(router_path, "w", encoding="utf-8") as f:
        f.write(content)


# 2. Update nodes.py
nodes_path = "ai_core/vlearn_ai/graph/nodes.py"
with open(nodes_path, "r", encoding="utf-8") as f:
    content = f.read()

if "general_knowledge_answer_node" not in content:
    content = content.replace(
        "from vlearn_ai.tools.give_direct_answer import execute_give_direct_answer",
        "from vlearn_ai.tools.give_direct_answer import execute_give_direct_answer\nfrom vlearn_ai.tools.give_general_answer import execute_give_general_answer"
    )

    node_code = """
# =====================================================================
# Node 5B: General Knowledge Answer
# =====================================================================
@_safe_node("general_knowledge_answer")
def general_knowledge_answer_node(
    state: LearningLoopState, model: BaseChatModel | None = None
) -> dict[str, Any]:
    \"\"\"Produce answer using general knowledge for out-of-context queries.\"\"\"
    query = state.get("user_query", "")
    if state.get("clarification_answer"):
        query = f"{query} (Làm rõ: {state.get('clarification_answer')})"

    context = state.get("selected_context", "")
    llm = model or get_generation_model()

    ans_obj = _run_async(execute_give_general_answer(query, context, llm))
    trace = _record_trace(state, "give_general_answer", "success", model=llm)

    return {
        "grounded_answer": ans_obj.answer,
        "grounded_claims": [],
        "citations": [],
        "candidate_answer": ans_obj.answer,
        "candidate_claims": [],
        "candidate_citations": [],
        "tool_trace": trace,
        "status": "running",
    }


# =====================================================================
# Node 6: Grounding Guard"""

    content = content.replace(
        "# =====================================================================\n# Node 6: Grounding Guard",
        node_code
    )

    with open(nodes_path, "w", encoding="utf-8") as f:
        f.write(content)


# 3. Update routes.py
routes_path = "ai_core/vlearn_ai/graph/routes.py"
with open(routes_path, "r", encoding="utf-8") as f:
    content = f.read()

if "out_of_context" not in content:
    content = content.replace(
        """def route_after_router(
    state: LearningLoopState,
) -> Literal["generate_clarification", "grounded_answer"]:""",
        """def route_after_router(
    state: LearningLoopState,
) -> Literal["generate_clarification", "grounded_answer", "general_knowledge_answer"]:"""
    )

    content = content.replace(
        """    route = state.get("route")
    if route == "clarify":
        return "generate_clarification"
    return "grounded_answer\"\"\"""",
        """    route = state.get("route")
    if route == "clarify":
        return "generate_clarification"
    if route == "out_of_context":
        return "general_knowledge_answer"
    return "grounded_answer\"\"\""""
    )
    
    # Actually wait, let's just do standard string replacement
    content = content.replace(
        '    route = state.get("route")\n    if route == "clarify":\n        return "generate_clarification"\n    return "grounded_answer"',
        '    route = state.get("route")\n    if route == "clarify":\n        return "generate_clarification"\n    if route == "out_of_context":\n        return "general_knowledge_answer"\n    return "grounded_answer"'
    )

    with open(routes_path, "w", encoding="utf-8") as f:
        f.write(content)


# 4. Update builder.py
builder_path = "ai_core/vlearn_ai/graph/builder.py"
with open(builder_path, "r", encoding="utf-8") as f:
    content = f.read()

if "general_knowledge_answer_node" not in content:
    content = content.replace(
        "    generate_clarification_node,\n    grounded_answer_node,",
        "    generate_clarification_node,\n    general_knowledge_answer_node,\n    grounded_answer_node,"
    )

    content = content.replace(
        "    def n_grounded_answer(state: LearningLoopState):\n        return grounded_answer_node(state, model=model)",
        "    def n_grounded_answer(state: LearningLoopState):\n        return grounded_answer_node(state, model=model)\n\n    def n_general_knowledge_answer(state: LearningLoopState):\n        return general_knowledge_answer_node(state, model=model)"
    )

    content = content.replace(
        '    builder.add_node("grounded_answer", n_grounded_answer)',
        '    builder.add_node("grounded_answer", n_grounded_answer)\n    builder.add_node("general_knowledge_answer", n_general_knowledge_answer)'
    )
    
    content = content.replace(
        '            "grounded_answer": "grounded_answer",\n            "failure": "failure",',
        '            "grounded_answer": "grounded_answer",\n            "general_knowledge_answer": "general_knowledge_answer",\n            "failure": "failure",'
    )

    content = content.replace(
        '    builder.add_conditional_edges(\n        "grounded_answer",',
        '    builder.add_edge("general_knowledge_answer", "output_guard")\n\n    builder.add_conditional_edges(\n        "grounded_answer",'
    )

    with open(builder_path, "w", encoding="utf-8") as f:
        f.write(content)

print("Patch applied successfully.")
