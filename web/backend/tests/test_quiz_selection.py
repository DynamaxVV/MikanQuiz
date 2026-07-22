"""Pure deterministic weighted draw behavior checks."""

import random

import pytest

from app.errors import ApiError
from app.models import Question
from app.services.quiz import select_questions


def make_question(question_id: int, difficulty: int) -> Question:
    """Create an unsaved model that has enough data for weighted selection only."""
    return Question(
        id=question_id,
        text=str(question_id),
        difficulty=difficulty,
        option_a="A",
        option_b="B",
        option_c="C",
        option_d="D",
        answer="A",
        explanation="解析",
    )


def test_weighted_selection_is_distinct_and_uses_a_smaller_available_pool() -> None:
    """Draws never repeat rows and uses all eligible questions when fewer exist."""
    questions = [make_question(index, index) for index in range(1, 6)]
    selected = select_questions(questions, 5, [1, 1, 1, 1, 1], random.Random(7))
    assert len({question.id for question in selected}) == 5
    smaller = select_questions(questions, 2, [0, 0, 100, 0, 0], random.Random(7))
    assert [question.id for question in smaller] == [3]
    with pytest.raises(ApiError) as error:
        select_questions(questions, 2, [0, 0, 0, 0, 0], random.Random(7))
    assert error.value.code == "QUIZ_NOT_ENOUGH_QUESTIONS"
