"""Pure deterministic question-selection behavior checks."""

import random

import pytest

from app.errors import ApiError
from app.models import Question, QuizAttempt
from app.services.quiz import select_questions


class FixedRandom:
    """Small deterministic random source for selecting a known weighted branch."""

    def __init__(self, value: float) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


def make_question(question_id: int, difficulty: int, font_id: int = 1) -> Question:
    """Create an unsaved model that has enough data for weighted selection only."""
    return Question(
        id=question_id,
        text=str(question_id),
        difficulty=difficulty,
        correct_option_id=font_id,
        explanation="解析",
    )


def test_selection_is_distinct_and_uses_a_smaller_available_pool() -> None:
    """Draws never repeat rows and uses all eligible questions when fewer exist."""
    questions = [make_question(index, index) for index in range(1, 4)]
    selected = select_questions(questions, 5, [1, 1, 1], random.Random(7))
    assert len({question.id for question in selected}) == 3
    smaller = select_questions(questions, 2, [0, 0, 100], random.Random(7))
    assert [question.id for question in smaller] == [3]
    with pytest.raises(ApiError) as error:
        select_questions(questions, 2, [0, 0, 0], random.Random(7))
    assert error.value.code == "QUIZ_NOT_ENOUGH_QUESTIONS"


def test_selection_uses_star_quotas_before_random_question_selection() -> None:
    """Relative settings become deterministic per-attempt star quotas."""
    questions = [
        make_question(1, 1, 1),
        make_question(2, 1, 2),
        make_question(3, 1, 3),
        make_question(4, 2, 4),
        make_question(5, 2, 5),
        make_question(6, 2, 6),
        make_question(7, 3, 7),
        make_question(8, 3, 8),
        make_question(9, 3, 9),
    ]

    selected = select_questions(questions, 6, [1, 1, 1], FixedRandom(0.2))

    assert {difficulty: sum(item.difficulty == difficulty for item in selected) for difficulty in (1, 2, 3)} == {1: 2, 2: 2, 3: 2}


def test_same_font_is_soft_limited_to_two_questions_per_attempt() -> None:
    """A third same-font question is allowed only when no other font remains."""
    questions = [
        make_question(question_id, 1, font_id)
        for font_id in range(1, 6)
        for question_id in range(font_id * 3, font_id * 3 + 3)
    ]

    selected = select_questions(questions, 10, [100, 0, 0], random.Random(4))

    counts = {}
    for question in selected:
        counts[question.correct_option_id] = counts.get(question.correct_option_id, 0) + 1
    assert max(counts.values()) <= 2

    small_pool = [make_question(question_id, 1, 1) for question_id in range(1, 6)]
    fallback = select_questions(small_pool, 5, [100, 0, 0], random.Random(4))
    assert len(fallback) == 5
    assert max(item.correct_option_id for item in fallback) == 1


def test_recent_fonts_and_questions_are_softly_downweighted() -> None:
    """Recent exposure prefers another font and another question when available."""
    font_questions = [make_question(1, 1, 1), make_question(2, 1, 2)]
    recent_font = QuizAttempt(question_ids=[1])
    selected_font = select_questions(
        font_questions,
        1,
        [100, 0, 0],
        FixedRandom(0.9),
        recent_attempts=[recent_font],
    )
    assert selected_font[0].id == 2

    same_font_questions = [make_question(1, 1, 1), make_question(2, 1, 1)]
    selected_question = select_questions(
        same_font_questions,
        1,
        [100, 0, 0],
        FixedRandom(0.5),
        recent_attempts=[recent_font],
    )
    assert selected_question[0].id == 2


def test_recent_history_is_limited_to_the_newest_three_attempts() -> None:
    """The fourth-oldest exposure is outside the recent-history window."""
    questions = [make_question(1, 1, 1), make_question(2, 1, 1)]
    attempts = [
        QuizAttempt(question_ids=[2]),
        QuizAttempt(question_ids=[2]),
        QuizAttempt(question_ids=[2]),
        QuizAttempt(question_ids=[1]),
    ]

    selected = select_questions(
        questions,
        1,
        [100, 0, 0],
        FixedRandom(0.49),
        recent_attempts=attempts,
    )

    assert selected[0].id == 1
