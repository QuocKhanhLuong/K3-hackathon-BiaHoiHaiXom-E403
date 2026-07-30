"""Tools package initialization for the 6 pedagogical tools."""

from vlearn_ai.tools.give_direct_answer import execute_give_direct_answer
from vlearn_ai.tools.give_example import ExampleOutput, execute_give_example
from vlearn_ai.tools.give_hint import HintOutput, execute_give_hint
from vlearn_ai.tools.motivate import MotivateOutput, execute_motivate
from vlearn_ai.tools.review_concept import execute_review_concept
from vlearn_ai.tools.validate_understanding import execute_validate_understanding

__all__ = [
    "ExampleOutput",
    "HintOutput",
    "MotivateOutput",
    "execute_give_direct_answer",
    "execute_give_example",
    "execute_give_hint",
    "execute_motivate",
    "execute_review_concept",
    "execute_validate_understanding",
]
