"""Scenario linter script ensuring evaluation quality and rejecting invalid scenarios."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from eval.config import SCENARIOS_DIR
from eval.schemas import ScenarioDefinition


def lint_scenario_files(scenarios_dir: Path = SCENARIOS_DIR) -> tuple[int, list[str]]:
    """Lint all scenario JSON files in directory and return error count and message list."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    total_count = 0

    if not scenarios_dir.exists():
        return 1, [f"Scenarios directory missing: {scenarios_dir}"]

    for json_file in sorted(scenarios_dir.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                errors.append(
                    f"File {json_file.name}: root content must be a list of scenarios"
                )
                continue

            for idx, item in enumerate(data, start=1):
                total_count += 1
                try:
                    scen = ScenarioDefinition(**item)
                except Exception as exc:  # noqa: BLE001 - scenario data boundary
                    errors.append(
                        f"File {json_file.name} [# {idx}]: Pydantic validation failed: {exc}"
                    )
                    continue

                # ID Uniqueness
                if scen.id in seen_ids:
                    errors.append(
                        f"Duplicate scenario ID '{scen.id}' in file {json_file.name}"
                    )
                seen_ids.add(scen.id)

                # Gold / Hard Scenario assertions depth check
                if scen.tier == "gold" and scen.evaluation_type == "hard":
                    for t_idx, turn in enumerate(scen.turns, start=1):
                        exp = turn.expected

                        # Check 1: Broad statuses rejection for gold hard scenario
                        if exp.statuses and len(exp.statuses) > 2:
                            errors.append(
                                f"Scenario '{scen.id}' Turn {t_idx}: Gold hard scenario has overly broad statuses {exp.statuses}"
                            )

                        # Check 2: At least one structural assertion beyond status/message
                        has_deep_assert = any(
                            [
                                exp.required_tools,
                                exp.allowed_tools,
                                exp.forbidden_tools,
                                exp.expected_tool_order,
                                exp.min_citations is not None,
                                exp.expected_citation_pages,
                                exp.min_followups is not None,
                                exp.grounding_required,
                                exp.new_check_required,
                                exp.no_stale_citations,
                                exp.required_source_ids,
                                exp.expected_failure_code,
                                exp.expected_blocked,
                            ]
                        )
                        if not has_deep_assert:
                            errors.append(
                                f"Scenario '{scen.id}' Turn {t_idx}: Gold hard scenario lacks structural assertions beyond status/message"
                            )

                # Tag-driven check consistency
                tags_lower = [t.lower() for t in scen.tags]
                if "failure_recovery" in tags_lower or "failure" in scen.id.lower():
                    has_fault = (
                        scen.offline_fixture and len(scen.offline_fixture.faults) > 0
                    )
                    has_exp_err = any(
                        t.expected.expected_failure_code or t.expected.expected_blocked
                        for t in scen.turns
                    )
                    if not has_fault and not has_exp_err:
                        errors.append(
                            f"Scenario '{scen.id}': Failure scenario lacks fault injection or failure expectations"
                        )

                if "cross_slide" in tags_lower or "cross" in scen.id.lower():
                    has_src_exp = any(
                        t.expected.required_source_ids
                        or t.expected.expected_citation_pages
                        for t in scen.turns
                    )
                    if not has_src_exp:
                        errors.append(
                            f"Scenario '{scen.id}': Cross-slide scenario lacks required source or page expectations"
                        )

        except Exception as exc:  # noqa: BLE001 - scenario file data boundary
            errors.append(f"File {json_file.name}: JSON parse error: {exc}")

    return len(errors), errors


def main():
    error_count, errors = lint_scenario_files()
    print("\n========================================================")
    print("  VLearn Scenario Linter")
    print("========================================================")

    if error_count == 0:
        print("  ✅ All scenario datasets passed linter checks successfully!\n")
        sys.exit(0)

    print(f"  ❌ Found {error_count} scenario lint errors:\n")
    for err in errors:
        print(f"    - {err}")
    print("\n========================================================\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
