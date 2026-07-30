"""Deterministic test double model for offline unit and flow tests."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field
from vlearn_ai.schemas import (
    CheckEvaluation,
    CheckOption,
    Citation,
    ClarificationRequest,
    FollowUp,
    FollowUpSuggestions,
    GroundedAnswer,
    InjectionAssessment,
    MicroCheck,
    RepairPlan,
    RouteOutput,
)
from vlearn_ai.tools.give_example import GiveExampleOutput
from vlearn_ai.tools.give_hint import GiveHintOutput
from vlearn_ai.tools.motivate import MotivateOutput


class DeterministicFakeChatModel(BaseChatModel):
    """Deterministic fake chat model returning typed Pydantic objects for with_structured_output."""

    route_to_return: str = "simple"
    is_injection: bool = False
    misconception_to_return: bool = False
    custom_responses: list[Any] = Field(default_factory=list)

    def _generate(
        self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any
    ) -> ChatResult:
        message_content = "Giải thích chi tiết theo tài liệu bài học."
        return ChatResult(
            generations=[
                ChatGeneration(message=BaseMessage(content=message_content, type="ai"))
            ]
        )

    async def _agenerate(
        self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any
    ) -> ChatResult:
        return self._generate(messages, stop=stop, **kwargs)

    @property
    def _llm_type(self) -> str:
        return "deterministic-fake-chat-model"

    def with_structured_output(self, schema: Any, **kwargs: Any):
        def _bind(input_val: Any):
            if schema == RouteOutput:
                return RouteOutput(
                    route=self.route_to_return,  # type: ignore
                    confidence=0.95,
                    reason="Test classification",
                )
            elif schema == InjectionAssessment:
                return InjectionAssessment(
                    injection_detected=self.is_injection,
                    confidence=0.99,
                    reason="Test assessment",
                )
            elif schema == ClarificationRequest:
                return ClarificationRequest(
                    clarification_question="Bạn có thể làm rõ câu hỏi không?",
                    reason="Ambiguous input",
                )
            elif schema == GroundedAnswer:
                return GroundedAnswer(
                    answer="Key dùng để so khớp với Query.",
                    citations=[
                        Citation(
                            citation_id="ctx_1",
                            snippet="Key dùng để so khớp với Query.",
                        )
                    ],
                )
            elif schema == MicroCheck:
                return MicroCheck(
                    question="Key có vai trò gì?",
                    question_type="multiple_choice",
                    target_concept="core_concept",
                    expected_answer="So khớp với Query.",
                    correct_option_id="opt_a",
                    options=[
                        CheckOption(option_id="opt_a", text="So khớp với Query."),
                        CheckOption(option_id="opt_b", text="Lưu dữ liệu đầu ra."),
                    ],
                    explanation="Giải thích đáp án đúng.",
                    evidence=["Key dùng để so khớp với Query."],
                )
            elif schema == CheckEvaluation:
                if self.misconception_to_return:
                    return CheckEvaluation(
                        is_correct=False,
                        score=0.0,
                        misconception_code="confuses_two_concepts",
                        error_explanation="Học viên nhầm lẫn giữa Key và Value.",
                        answer_evidence="Key và Value là một",
                        recommended_repair_strategy="review_concept_and_example",
                    )
                else:
                    return CheckEvaluation(
                        is_correct=True,
                        score=1.0,
                        misconception_code="none",
                        error_explanation="Học viên đúng.",
                        answer_evidence="Đáp án A",
                        recommended_repair_strategy="none",
                    )
            elif schema == RepairPlan:
                return RepairPlan(
                    misconception_code="confuses_two_concepts",
                    recommended_strategy="review_concept_and_example",
                    planned_tools=["review_concept", "give_example"],
                )
            elif schema == FollowUpSuggestions:
                return FollowUpSuggestions(
                    followups=[
                        FollowUp(
                            label="Hiểu sâu hơn", question="Cơ chế chi tiết là gì?"
                        ),
                        FollowUp(label="Ví dụ", question="Cho thêm ví dụ?"),
                    ]
                )
            elif schema == GiveExampleOutput:
                return GiveExampleOutput(
                    example="Ví dụ minh họa Key-Value",
                    relevance_explanation="Liên quan bài học",
                )
            elif schema == GiveHintOutput:
                return GiveHintOutput(
                    hint="Gợi ý từng bước",
                    hint_level=1,
                    guiding_question="Bạn có nhớ khái niệm không?",
                )
            elif schema == MotivateOutput:
                return MotivateOutput(
                    message="Cố lên bạn ơi!",
                    acknowledged_difficulty="Khó khăn",
                    next_small_step="Đọc lại bài",
                )
            elif issubclass(schema, BaseModel):
                return schema()
            return {}

        return RunnableLambda(_bind)
