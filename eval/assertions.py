"""Hard deterministic assertion engine for VLearn AI Core evaluation."""

from __future__ import annotations

import difflib

from eval.config import GENERIC_FOLLOWUP_PATTERNS, INFRASTRUCTURE_TOOLS
from eval.schemas import AssertionResult, TurnExecutionResult, TurnExpectations


def _string_similarity(a: str, b: str) -> float:
    """Calculate SequenceMatcher similarity ratio between two strings."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


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

    tool_seq = turn_res.tool_sequence

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
    if expected.required_tools:
        missing = [t for t in expected.required_tools if t not in tool_seq]
        passed = len(missing) == 0
        msg = f"Missing required tools: {missing}. Executed: {tool_seq}"
        _add("required_tools", passed, msg, "tool_selection")

    # 4. Allowed Tools
    if expected.allowed_tools is not None:
        req_set = set(expected.required_tools or [])
        allowed_set = set(expected.allowed_tools) | req_set | set(INFRASTRUCTURE_TOOLS)
        unnecessary = [t for t in tool_seq if t not in allowed_set]
        passed = len(unnecessary) == 0
        msg = f"Unallowed tools executed: {unnecessary}. Allowed set: {allowed_set}"
        _add("allowed_tools", passed, msg, "tool_selection")

    # 5. Forbidden Tools
    if expected.forbidden_tools:
        found_forbidden = [t for t in expected.forbidden_tools if t in tool_seq]
        passed = len(found_forbidden) == 0
        msg = f"Forbidden tools executed: {found_forbidden}"
        _add("forbidden_tools", passed, msg, "tool_selection")

    # 6. Expected Tool Order
    if expected.expected_tool_order:
        order_passed = True
        order_msgs = []
        for pair in expected.expected_tool_order:
            if len(pair) == 2:
                t1, t2 = pair[0], pair[1]
                t1_in = t1 in tool_seq
                t2_in = t2 in tool_seq

                if not t1_in or not t2_in:
                    order_passed = False
                    missing = [t for t in (t1, t2) if t not in tool_seq]
                    order_msgs.append(f"Pair [{t1}, {t2}] failed: missing tool(s) {missing}")
                else:
                    idx1 = tool_seq.index(t1)
                    idx2 = tool_seq.index(t2)
                    if idx1 >= idx2:
                        order_passed = False
                        order_msgs.append(f"'{t1}' (index {idx1}) came after '{t2}' (index {idx2})")
        msg = "Tool order verified" if order_passed else "; ".join(order_msgs)
        _add("expected_tool_order", order_passed, msg, "tool_order")

    # 7. Assistant Message Requirement
    if expected.assistant_message_required is True:
        has_msg = bool(turn_res.assistant_message and turn_res.assistant_message.strip())
        msg = "Assistant message present" if has_msg else "Assistant message is missing or empty"
        _add("assistant_message_required", has_msg, msg, "general")

    # 8. Grounding Required
    if expected.grounding_required is True:
        has_cits = len(turn_res.citation_ids) > 0
        guard_ran = "grounding_guard" in tool_seq
        status_ok = turn_res.status not in ("failed", "grounding_failure")
        valid_sources = True
        if turn_res.retrieved_sources and turn_res.citation_ids:
            # Source IDs check
            retrieved_set = set(turn_res.retrieved_sources)
            for cid in turn_res.citation_ids:
                if cid not in retrieved_set and not any(r.endswith(cid) or cid.endswith(r) for r in retrieved_set):
                    valid_sources = False
                    break
        passed = has_cits and guard_ran and status_ok and valid_sources
        msg = (
            "Grounding verified"
            if passed
            else f"Grounding check failed (citations={has_cits}, guard_ran={guard_ran}, status_ok={status_ok}, valid_sources={valid_sources})"
        )
        _add("grounding_required", passed, msg, "grounding")

    # 9. Citations Count & Pages
    num_citations = len(turn_res.citation_ids)
    if expected.min_citations is not None:
        passed = num_citations >= expected.min_citations
        msg = f"Expected min {expected.min_citations} citations, got {num_citations}"
        _add("min_citations", passed, msg, "citation")

    if expected.max_citations is not None:
        passed = num_citations <= expected.max_citations
        msg = f"Expected max {expected.max_citations} citations, got {num_citations}"
        _add("max_citations", passed, msg, "citation")

    if expected.expected_citation_pages:
        actual_pages = set(turn_res.citation_pages)
        expected_pages = set(expected.expected_citation_pages)
        passed = expected_pages.issubset(actual_pages)
        msg = f"Expected citation pages subset {expected.expected_citation_pages}, got {turn_res.citation_pages}"
        _add("expected_citation_pages", passed, msg, "citation")

    # 10. Source & Deck Requirements
    retrieved_sources = set(turn_res.retrieved_sources)
    if expected.required_source_ids:
        req_sources = set(expected.required_source_ids)
        passed = req_sources.issubset(retrieved_sources)
        msg = f"Required sources subset {expected.required_source_ids}, got retrieved {list(retrieved_sources)}"
        _add("required_source_ids", passed, msg, "retrieval")

    if expected.forbidden_source_ids:
        forbid_sources = set(expected.forbidden_source_ids)
        intersection = forbid_sources.intersection(retrieved_sources)
        passed = len(intersection) == 0
        msg = f"Forbidden sources retrieved: {list(intersection)}"
        _add("forbidden_source_ids", passed, msg, "retrieval")

    if expected.required_deck_ids or expected.forbidden_deck_ids:
        retrieved_decks = set()
        for src in retrieved_sources:
            if "-" in src:
                retrieved_decks.add(src.split("-")[0])

        if expected.required_deck_ids:
            passed = set(expected.required_deck_ids).issubset(retrieved_decks)
            msg = f"Required decks subset {expected.required_deck_ids}, got {list(retrieved_decks)}"
            _add("required_deck_ids", passed, msg, "retrieval")

        if expected.forbidden_deck_ids:
            intersection = set(expected.forbidden_deck_ids).intersection(retrieved_decks)
            passed = len(intersection) == 0
            msg = f"Forbidden decks retrieved: {list(intersection)}"
            _add("forbidden_deck_ids", passed, msg, "retrieval")

    # 11. Followups Assertions
    num_followups = len(turn_res.followups)
    if expected.min_followups is not None:
        passed = num_followups >= expected.min_followups
        msg = f"Expected min {expected.min_followups} followups, got {num_followups}"
        _add("min_followups", passed, msg, "followup")

    if expected.max_followups is not None:
        passed = num_followups <= expected.max_followups
        msg = f"Expected max {expected.max_followups} followups, got {num_followups}"
        _add("max_followups", passed, msg, "followup")

    if expected.followup_schema_required is True and num_followups > 0:
        valid_schema = all(
            isinstance(f, dict) and bool(f.get("label")) and bool(f.get("question"))
            for f in turn_res.followups
        )
        msg = "Followup schema valid" if valid_schema else "Followups missing label or question"
        _add("followup_schema_required", valid_schema, msg, "followup")

    if expected.followups_unique is True and num_followups > 0:
        q_texts = [str(f.get("question", "")).strip().lower() for f in turn_res.followups]
        unique_passed = len(q_texts) == len(set(q_texts))
        msg = "All followups are unique" if unique_passed else "Duplicate followup questions detected"
        _add("followups_unique", unique_passed, msg, "followup")

    if expected.followups_not_duplicate_query is True and num_followups > 0:
        user_q = turn_res.input_text.strip().lower()
        no_dup_q = not any(_string_similarity(str(f.get("question", "")), user_q) > 0.85 for f in turn_res.followups)
        msg = "No followup duplicates user query" if no_dup_q else "Followup question duplicates user query"
        _add("followups_not_duplicate_query", no_dup_q, msg, "followup")

    if expected.followups_not_duplicate_answer is True and num_followups > 0:
        ans_text = str(turn_res.assistant_message or "").strip().lower()
        no_dup_ans = not any(_string_similarity(str(f.get("question", "")), ans_text) > 0.85 for f in turn_res.followups)
        msg = "No followup duplicates assistant answer" if no_dup_ans else "Followup question duplicates assistant answer"
        _add("followups_not_duplicate_answer", no_dup_ans, msg, "followup")

    if (expected.generic_followups_forbidden is True or expected.min_followups is not None) and num_followups > 0:
        generic_found = False
        for f in turn_res.followups:
            q_text = str(f.get("question", "")).lower()
            if any(pattern in q_text for pattern in GENERIC_FOLLOWUP_PATTERNS):
                generic_found = True
                break
        msg = "No generic followups detected" if not generic_found else "Generic followup pattern detected"
        _add("generic_followups_forbidden", not generic_found, msg, "followup")

    # 12. Stale Citations Check
    if expected.no_stale_citations is True:
        stale_passed = True
        stale_msg = "No stale citations"
        if turn_res.citation_ids:
            retrieved_set = set(turn_res.retrieved_sources)
            # Check if any citation is not backed by current retrieved sources
            for cid in turn_res.citation_ids:
                if retrieved_set and cid not in retrieved_set and not any(r.endswith(cid) or cid.endswith(r) for r in retrieved_set):
                    stale_passed = False
                    stale_msg = f"Citation '{cid}' is stale / not in current retrieved sources {list(retrieved_set)}"
                    break

            if stale_passed and previous_turn_res and previous_turn_res.citation_ids:
                prev_cit_set = set(previous_turn_res.citation_ids)
                curr_cit_set = set(turn_res.citation_ids)
                # If question changed but citations are identical and ungrounded
                if prev_cit_set == curr_cit_set and turn_res.input_text != previous_turn_res.input_text and not turn_res.retrieved_sources:
                    stale_passed = False
                    stale_msg = "Stale citations reused from previous turn state without context grounding"

        _add("no_stale_citations", stale_passed, stale_msg, "state_leak")

    # 13. New Check Required
    if expected.new_check_required is True:
        has_check = turn_res.status == "awaiting_check" and bool(turn_res.check_question or turn_res.check_id)
        is_distinct = True
        if has_check and previous_turn_res and previous_turn_res.check_question:
            sim = _string_similarity(turn_res.check_question or "", previous_turn_res.check_question or "")
            if sim > 0.85 or (turn_res.check_id and turn_res.check_id == previous_turn_res.check_id):
                is_distinct = False

        passed = has_check and is_distinct
        msg = (
            "New distinct check generated"
            if passed
            else f"New check evaluation failed (has_check={has_check}, distinct={is_distinct})"
        )
        _add("new_check_required", passed, msg, "repair")

    # 14. No Duplicate Action
    if expected.no_duplicate_action is True and previous_turn_res:
        prev_act = previous_turn_res.action_id or previous_turn_res.check_id
        curr_act = turn_res.action_id or turn_res.check_id
        is_dup = bool(prev_act and curr_act and prev_act == curr_act and turn_res.status == previous_turn_res.status)
        msg = "No duplicate action" if not is_dup else f"Duplicate action ID '{curr_act}' recreated"
        _add("no_duplicate_action", not is_dup, msg, "multi_turn")

    # 15. Max Tool Calls & Latency
    if expected.max_tool_calls is not None:
        passed = len(tool_seq) <= expected.max_tool_calls
        msg = f"Tool calls count {len(tool_seq)} <= max {expected.max_tool_calls}"
        _add("max_tool_calls", passed, msg, "reliability")

    if expected.max_latency_ms is not None:
        passed = turn_res.latency_ms <= expected.max_latency_ms
        msg = f"Latency {turn_res.latency_ms} ms <= max {expected.max_latency_ms} ms"
        _add("max_latency_ms", passed, msg, "latency")

    # 16. Expected Failure Code & Blocked
    if expected.expected_failure_code:
        err_msg = str(turn_res.error_message or "")
        passed = expected.expected_failure_code in err_msg or turn_res.status in ("failed", "grounding_failure")
        msg = f"Expected failure code '{expected.expected_failure_code}', got error '{err_msg}'"
        _add("expected_failure_code", passed, msg, "exception")

    if expected.expected_blocked is True:
        passed = turn_res.status == "blocked"
        msg = "Expected status to be blocked" if passed else f"Expected blocked status, got '{turn_res.status}'"
        _add("expected_blocked", passed, msg, "reliability")

    # 17. Response Text Matching
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
