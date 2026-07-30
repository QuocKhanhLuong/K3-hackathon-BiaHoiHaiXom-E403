"""Deterministic fake ChatModel test double for VLearn AI Core tests."""

from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field
from vlearn_ai.schemas import (
    CheckEvaluation,
    CheckOption,
    Citation,
    ClarificationRequest,
    FollowUp,
    FollowUpSuggestions,
    GiveExampleOutput,
    GiveHintOutput,
    GroundedAnswer,
    InjectionAssessment,
    MicroCheck,
    MotivateOutput,
    RepairPlan,
    RouteOutput,
)


class DeterministicFakeChatModel(BaseChatModel):
    """Deterministic fake ChatModel for offline testing."""

    route_to_return: str = "simple"
    misconception_to_return: bool = False
    is_injection: bool = False
    custom_responses: list[Any] = Field(default_factory=list)
    model_script: list[Any] = Field(default_factory=list)
    faults: list[Any] = Field(default_factory=list)
    faults_triggered: list[str] = Field(default_factory=list)
    scenario_id: str = ""

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        gen = ChatGeneration(
            message=BaseMessage(content="Fake response", type="assistant")
        )
        return ChatResult(generations=[gen])

    @property
    def _llm_type(self) -> str:
        return "deterministic-fake-chat-model"

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        """Return a runnable returning deterministic typed model based on schema."""

        def _bind(input_val: Any) -> Any:
            input_str = str(input_val)
            schema_name = getattr(schema, "__name__", str(schema))

            # 1. Fault Injection Check
            tool_mapping = {
                "InjectionAssessment": "context_guard",
                "RouteOutput": "router",
                "ClarificationRequest": "generate_clarification",
                "GroundedAnswer": "give_direct_answer",
                "MicroCheck": "generate_check",
                "CheckEvaluation": "evaluate_check",
                "RepairPlan": "repair_misconception",
                "GiveExampleOutput": "give_example",
                "GiveHintOutput": "give_hint",
                "MotivateOutput": "motivate",
                "FollowUpSuggestions": "suggest_followups",
            }
            target_tool = tool_mapping.get(schema_name, schema_name)

            for f in self.faults:
                f_target = f.get("target") if isinstance(f, dict) else getattr(f, "target", "")
                f_type = f.get("type") if isinstance(f, dict) else getattr(f, "type", "")
                f_exc = f.get("exception") if isinstance(f, dict) else getattr(f, "exception", None)

                if f_target in (schema_name, target_tool):
                    if f_target not in self.faults_triggered:
                        self.faults_triggered.append(f_target)
                    if f_type == "raise":
                        raise RuntimeError(f_exc or f"Injected fault raise on {f_target}")
                    if f_type == "timeout":
                        raise TimeoutError(f"Injected timeout fault on {f_target}")
                    if f_type == "invalid_structured_output":
                        raise ValueError(f"Injected invalid structured output on {f_target}")
                    if f_type == "empty_output":
                        return schema()

            # 2. Scripted Output Fixture Check
            if self.model_script:
                for idx, script_item in enumerate(self.model_script):
                    if isinstance(script_item, dict):
                        s_name = script_item.get("schema") or script_item.get("schema_name")
                    else:
                        s_name = getattr(script_item, "schema_name", "")
                        if callable(s_name):
                            s_name = ""

                    s_out = (
                        script_item.get("output")
                        if isinstance(script_item, dict)
                        else getattr(script_item, "output", {})
                    )
                    if s_name in (schema_name, target_tool):
                        # Consume item to handle multi-turn progression
                        self.model_script.pop(idx)
                        return schema(**s_out)

                if schema == InjectionAssessment:
                    return InjectionAssessment(
                        injection_detected=self.is_injection,
                        confidence=0.99 if self.is_injection else 0.05,
                        reason="Deterministic test assessment",
                    )

                raise RuntimeError(
                    f"missing_fixture_output: No scripted output for schema '{schema_name}' in scenario '{self.scenario_id}'"
                )

            if schema == InjectionAssessment:
                return InjectionAssessment(
                    injection_detected=self.is_injection,
                    confidence=0.99 if self.is_injection else 0.05,
                    reason="Deterministic test assessment",
                )

            if schema == RouteOutput:
                return RouteOutput(
                    route=self.route_to_return,  # type: ignore
                    confidence=0.95,
                    reason="Test classification",
                )

            if schema == ClarificationRequest:
                return ClarificationRequest(
                    clarification_question="Bạn có thể làm rõ khía cạnh nào bạn muốn tìm hiểu không?",
                    reason="Ambiguous context",
                )

            if schema == GroundedAnswer:
                return GroundedAnswer(
                    answer="Key dùng để so khớp với Query.",
                    claims=[
                        {
                            "claim": "Key dùng để so khớp với Query.",
                            "citation_ids": ["ctx_1"],
                        }
                    ],
                    citations=[
                        Citation(
                            citation_id="ctx_1",
                            snippet="Key dùng để so khớp với Query.",
                        )
                    ],
                )

            if schema == MicroCheck:
                if "Value có vai trò gì" in input_str:
                    return MicroCheck(
                        question="Cơ chế Attention tính toán điểm như thế nào?",
                        question_type="multiple_choice",
                        target_concept="Attention Weight",
                        expected_answer="Tính tương quan giữa Q và K.",
                        correct_option_id="opt_a",
                        options=[
                            CheckOption(
                                option_id="opt_a", text="Tính tương quan giữa Q và K."
                            ),
                            CheckOption(option_id="opt_b", text="Lưu dữ liệu."),
                            CheckOption(option_id="opt_c", text="Tính softmax."),
                        ],
                        explanation="Attention tính tương quan giữa Q và K.",
                        evidence=["Key dùng để so khớp với Query."],
                    )

                if "Câu hỏi cũ" in input_str:
                    return MicroCheck(
                        question="Value có vai trò gì trong Transformer?",
                        question_type="multiple_choice",
                        target_concept="Transformer Value",
                        expected_answer="Lưu thông tin nội dung.",
                        correct_option_id="opt_a",
                        options=[
                            CheckOption(
                                option_id="opt_a", text="Lưu thông tin nội dung."
                            ),
                            CheckOption(option_id="opt_b", text="So khớp với Query."),
                            CheckOption(option_id="opt_c", text="Tính điểm chú ý."),
                        ],
                        explanation="Value (V) chứa thông tin nội dung.",
                        evidence=["Key dùng để so khớp với Query."],
                    )

                return MicroCheck(
                    question="Key có vai trò gì?",
                    question_type="multiple_choice",
                    target_concept="Transformer Key",
                    expected_answer="So khớp với Query.",
                    correct_option_id="opt_a",
                    options=[
                        CheckOption(option_id="opt_a", text="So khớp với Query."),
                        CheckOption(option_id="opt_b", text="Lưu dữ liệu đầu ra."),
                        CheckOption(option_id="opt_c", text="Tính điểm chú ý."),
                    ],
                    explanation="Key (K) dùng để so khớp với Query (Q).",
                    evidence=["Key dùng để so khớp với Query."],
                )

            if schema == CheckEvaluation:
                if self.misconception_to_return:
                    return CheckEvaluation(
                        is_correct=False,
                        score=0.0,
                        misconception_code="key_value_confusion",
                        error_explanation="Học viên nhầm lẫn giữa Key và Value.",
                        answer_evidence="Nhầm lẫn",
                        recommended_repair_strategy="review_concept_and_example",
                    )
                return CheckEvaluation(
                    is_correct=True,
                    score=1.0,
                    misconception_code="none",
                    error_explanation="Học viên trả lời đúng.",
                    answer_evidence="opt_a",
                    recommended_repair_strategy="none",
                )

            if schema == RepairPlan:
                return RepairPlan(
                    misconception_code="key_value_confusion",
                    recommended_strategy="review_concept_and_example",
                    planned_tools=["review_concept", "give_example"],
                )

            if schema == GiveExampleOutput:
                return GiveExampleOutput(
                    example="Ví dụ minh họa Key-Value",
                    relevance_explanation="Giúp minh họa khái niệm",
                )

            if schema == GiveHintOutput:
                return GiveHintOutput(
                    hint="Hãy xem lại vai trò của Key.",
                    hint_level=1,
                    guiding_question="Key dùng để làm gì?",
                )

            if schema == MotivateOutput:
                return MotivateOutput(
                    message="Cố lên! Bạn đang làm rất tốt.",
                    acknowledged_difficulty="Khái niệm này tương đối mới",
                    next_small_step="Hãy thử lại câu hỏi tiếp theo.",
                )

            if schema == FollowUpSuggestions:
                return FollowUpSuggestions(
                    followups=[
                        FollowUp(
                            label="Hiểu sâu hơn", question="Cơ chế chi tiết là gì?"
                        ),
                        FollowUp(label="Ví dụ", question="Cho thêm ví dụ?"),
                    ]
                )

            return schema()

        return RunnableLambda(_bind)
