"""Hard deterministic assertion engine for VLearn AI Core evaluation."""

from __future__ import annotations

from eval.config import GENERIC_FOLLOWUP_PATTERNS
from eval.schemas import AssertionResult, TurnExecutionResult, TurnExpectations


def evaluate_turn_assertions(
    turn_res: TurnExecutionResult,
    expected: TurnExpectations,
    previous_turn_res: TurnExecutionResult | None = None,
) -> list[AssertionResult]:
    """Evaluate hard deterministic assertions against turn execution output."""
    results: list[AssertionResult] = []

    def _add(name: str, passed: bool, msg: str, category: str):
        results.append(
            AssertionResult(name=name, passed=passed, message=msg, category=category)
        )

    # 1. Route Assertion
    if expected.routes:
        actual_route = turn_res.route
        passed = actual_route in expected.routes
        msg = f"Expected route in {expected.routes}, got '{actual_route}'"
        _add("route_check", passed, msg, "routing")

    # 2. Status Assertion
    if expected.statuses:
        actual_status = turn_res.status
        passed = actual_status in expected.statuses
        msg = f"Expected status in {expected.statuses}, got '{actual_status}'"
        _add("status_check", passed, msg, "multi_turn")

    # 3. Required Tools
    tool_seq = turn_res.tool_sequence
    if expected.required_tools:
        missing = [t for t in expected.required_tools if t not in tool_seq]
        passed = len(missing) == 0
        msg = f"Missing required tools: {missing}. Executed: {tool_seq}"
        _add("required_tools", passed, msg, "tool_selection")

    # 4. Forbidden Tools
    if expected.forbidden_tools:
        found_forbidden = [t for t in expected.forbidden_tools if t in tool_seq]
        passed = len(found_forbidden) == 0
        msg = f"Forbidden tools executed: {found_forbidden}"
        _add("forbidden_tools", passed, msg, "tool_selection")

    # 5. Partial Tool Ordering
    if expected.expected_tool_order:
        order_passed = True
        order_msgs = []
        for pair in expected.expected_tool_order:
            if len(pair) == 2:
                t1, t2 = pair[0], pair[1]
                if t1 in tool_seq and t2 in tool_seq:
                    idx1 = tool_seq.index(t1)
                    idx2 = tool_seq.index(t2)
                    if idx1 >= idx2:
                        order_passed = False
                        order_msgs.append(f"'{t1}' (index {idx1}) came after '{t2}' (index {idx2})")
        msg = "Tool order verified" if order_passed else "; ".join(order_msgs)
        _add("tool_order", order_passed, msg, "tool_order")

    # 6. Assistant Message Requirement
    if expected.assistant_message_required is True:
        has_msg = bool(turn_res.assistant_message and turn_res.assistant_message.strip())
        msg = "Assistant message present" if has_msg else "Assistant message is missing or empty"
        _add("assistant_message_required", has_msg, msg, "general")

    # 7. Grounding & Citations Count
    num_citations = len(turn_res.citation_ids)
    if expected.min_citations is not None:
        passed = num_citations >= expected.min_citations
        msg = f"Expected min {expected.min_citations} citations, got {num_citations}"
        _add("min_citations", passed, msg, "citation")

    if expected.max_citations is not None:
        passed = num_citations <= expected.max_citations
        msg = f"Expected max {expected.max_citations} citations, got {num_citations}"
        _add("max_citations", passed, msg, "citation")

    # 8. Expected Citation Pages
    if expected.expected_citation_pages:
        actual_pages = set(turn_res.citation_pages)
        expected_pages = set(expected.expected_citation_pages)
        matched = expected_pages.intersection(actual_pages)
        passed = len(matched) > 0
        msg = f"Expected citation pages {expected.expected_citation_pages}, found {turn_res.citation_pages}"
        _add("citation_pages", passed, msg, "citation")

    # 9. Followups Count
    num_followups = len(turn_res.followups)
    if expected.min_followups is not None:
        passed = num_followups >= expected.min_followups
        msg = f"Expected min {expected.min_followups} followups, got {num_followups}"
        _add("min_followups", passed, msg, "followup")

    if expected.max_followups is not None:
        passed = num_followups <= expected.max_followups
        msg = f"Expected max {expected.max_followups} followups, got {num_followups}"
        _add("max_followups", passed, msg, "followup")

    # 10. Generic Followups Check
    if num_followups > 0:
        generic_found = False
        for f in turn_res.followups:
            q_text = str(f.get("question", "")).lower()
            if any(pattern in q_text for pattern in GENERIC_FOLLOWUP_PATTERNS):
                generic_found = True
                break
        msg = "Followups are specific" if not generic_found else "Generic followup pattern detected"
        _add("generic_followups", not generic_found, msg, "followup")

    # 11. Stale Citations Check
    if expected.no_stale_citations is True and previous_turn_res:
        prev_cit_set = set(previous_turn_res.citation_ids)
        curr_cit_set = set(turn_res.citation_ids)
        # If current turn has citations, check they are not exact duplicate stale copies of previous
        is_stale = prev_cit_set and prev_cit_set == curr_cit_set
        msg = "No stale citations detected" if not is_stale else "Stale citations reused from previous turn"
        _add("no_stale_citations", not is_stale, msg, "state_leak")

    # 12. New Check Required
    if expected.new_check_required is True:
        has_check = turn_res.status == "awaiting_check"
        msg = "New check generated" if has_check else "Expected new check question but got none"
        _add("new_check_required", has_check, msg, "repair")

    # 13. Max Tool Calls
    if expected.max_tool_calls is not None:
        passed = len(tool_seq) <= expected.max_tool_calls
        msg = f"Tool calls count {len(tool_seq)} <= max {expected.max_tool_calls}"
        _add("max_tool_calls", passed, msg, "reliability")

    # 14. Max Latency
    if expected.max_latency_ms is not None:
        passed = turn_res.latency_ms <= expected.max_latency_ms
        msg = f"Latency {turn_res.latency_ms} ms <= max {expected.max_latency_ms} ms"
        _add("max_latency_ms", passed, msg, "latency")

    # 15. Expected Failure Code / Blocked
    if expected.expected_failure_code:
        err_msg = str(turn_res.error_message or "")
        passed = expected.expected_failure_code in err_msg or turn_res.status == "failed"
        msg = f"Expected failure code {expected.expected_failure_code}"
        _add("expected_failure_code", passed, msg, "exception")

    if expected.expected_blocked is True:
        passed = turn_res.status == "blocked"
        msg = "Expected status to be blocked" if passed else f"Expected blocked status, got {turn_res.status}"
        _add("expected_blocked", passed, msg, "reliability")

    # 16. Response Text Matching
    ans_text = turn_res.assistant_message or ""
    if expected.response_contains_any:
        found_any = any(term.lower() in ans_text.lower() for term in expected.response_contains_any)
        msg = f"Response contains at least one of {expected.response_contains_any}"
        _add("response_contains_any", found_any, msg, "general")

    if expected.response_contains_all:
        found_all = all(term.lower() in ans_text.lower() for term in expected.response_contains_all)
        msg = f"Response contains all of {expected.response_contains_all}"
        _add("response_contains_all", found_all, msg, "general")

    if expected.response_not_contains:
        found_forbidden = [t for t in expected.response_not_contains if t.lower() in ans_text.lower()]
        passed = len(found_forbidden) == 0
        msg = f"Response contains forbidden text: {found_forbidden}"
        _add("response_not_contains", passed, msg, "general")

    return results
