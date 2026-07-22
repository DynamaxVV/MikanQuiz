"""Anonymous attempt selection, strict grading and idempotent submission."""

from datetime import timedelta
import random
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import (
    Question,
    QuizAttempt,
    Submission,
    SubmissionAnswer,
    as_utc,
    utc_now,
)
from app.schemas import AttemptSubmit, PublicQuestion, SubmissionResult
from app.security import hash_token, new_token
from app.services.questions import get_settings
from app.services.serializers import public_question, submission_result


class RandomSource(Protocol):
    """The small random surface needed by weighted selection tests."""

    def random(self) -> float:
        """Return a pseudo-random value in the half-open unit interval."""


def create_attempt(
    session: Session, mode: str, random_source: RandomSource | None = None
) -> tuple[str, QuizAttempt, list[PublicQuestion]]:
    """Bind a random eligible subset to one opaque 24-hour attempt token."""
    settings = get_settings(session)
    questions = session.scalars(select(Question)).all()
    selected = select_questions(
        questions, settings.question_count, settings.modes[mode], random_source
    )
    token = new_token()
    attempt = QuizAttempt(
        token_hash=hash_token(token),
        mode=mode,
        question_ids=[question.id for question in selected],
        expires_at=utc_now() + timedelta(hours=24),
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return token, attempt, [public_question(question) for question in selected]


def select_questions(
    questions: list[Question], count: int, weights: list[int], random_source: RandomSource | None = None
) -> list[Question]:
    """Choose distinct questions by difficulty weight without replacement."""
    eligible = [question for question in questions if weights[question.difficulty - 1] > 0]
    if not eligible:
        raise ApiError(
            409,
            "QUIZ_NOT_ENOUGH_QUESTIONS",
            "当前难度没有可用题目，请录入符合该难度权重的题目或调整出题策略",
        )
    count = min(count, len(eligible))
    source = random_source or random.SystemRandom()
    selected: list[Question] = []
    while len(selected) < count:
        question = _weighted_pop(eligible, weights, source)
        selected.append(question)
    return selected


def _weighted_pop(
    candidates: list[Question], weights: list[int], random_source: RandomSource
) -> Question:
    """Remove one candidate using its current star weight as its probability."""
    total = sum(weights[item.difficulty - 1] for item in candidates)
    cursor = random_source.random() * total
    for index, question in enumerate(candidates):
        cursor -= weights[question.difficulty - 1]
        if cursor < 0:
            return candidates.pop(index)
    return candidates.pop()


def current_attempt(session: Session, token: str) -> tuple[QuizAttempt, list[PublicQuestion]]:
    """Return an unfinished unexpired attempt without leaking answer fields."""
    attempt = get_attempt(session, token)
    if attempt.submitted_at is not None:
        raise ApiError(409, "ATTEMPT_ALREADY_SUBMITTED", "本次答题已经提交")
    ensure_unexpired(attempt)
    return attempt, attempt_questions(session, attempt)


def submit_attempt(
    session: Session, token: str, data: AttemptSubmit
) -> SubmissionResult:
    """Score exactly one attempt's bound questions and persist immutable snapshots."""
    attempt = get_attempt(session, token)
    existing = submission_for_attempt(session, attempt.id)
    if existing is not None:
        return stored_result(session, existing)
    ensure_unexpired(attempt)
    questions = attempt_questions_models(session, attempt)
    validate_answers(data.answers, questions)
    submission = build_submission(attempt, data, questions)
    session.add(submission)
    session.flush()
    persist_answer_snapshots(session, submission, questions, data.answers)
    attempt.submitted_at = utc_now()
    session.commit()
    return stored_result(session, submission)


def get_attempt(session: Session, token: str) -> QuizAttempt:
    """Resolve an opaque client token without storing or returning it."""
    if not token:
        raise ApiError(401, "ATTEMPT_TOKEN_REQUIRED", "缺少答题会话")
    attempt = session.scalar(
        select(QuizAttempt).where(QuizAttempt.token_hash == hash_token(token))
    )
    if attempt is None:
        raise ApiError(404, "ATTEMPT_NOT_FOUND", "答题会话不存在")
    return attempt


def ensure_unexpired(attempt: QuizAttempt) -> None:
    """Reject a resume or first submit after the documented 24-hour lifetime."""
    if as_utc(attempt.expires_at) <= utc_now():
        raise ApiError(410, "ATTEMPT_EXPIRED", "本次答题已过期，请重新开始")


def attempt_questions(session: Session, attempt: QuizAttempt) -> list[PublicQuestion]:
    """Resolve bound questions in their original randomized order for a client."""
    return [public_question(question) for question in attempt_questions_models(session, attempt)]


def attempt_questions_models(session: Session, attempt: QuizAttempt) -> list[Question]:
    """Load all bound questions and fail loudly if data integrity was broken."""
    rows = session.scalars(select(Question).where(Question.id.in_(attempt.question_ids))).all()
    by_id = {question.id: question for question in rows}
    try:
        return [by_id[question_id] for question_id in attempt.question_ids]
    except KeyError as error:
        raise ApiError(409, "ATTEMPT_QUESTION_MISSING", "答题题目已被移除") from error


def validate_answers(answers: dict[int, str], questions: list[Question]) -> None:
    """Require exactly one valid option for every and only bound question ID."""
    expected_ids = {question.id for question in questions}
    if set(answers) != expected_ids:
        raise ApiError(422, "INVALID_ANSWERS", "答案必须完整且只能包含本次题目")
    if any(answer not in {"A", "B", "C", "D"} for answer in answers.values()):
        raise ApiError(422, "INVALID_ANSWERS", "答案选项不正确")


def build_submission(
    attempt: QuizAttempt, data: AttemptSubmit, questions: list[Question]
) -> Submission:
    """Calculate integer scoring only from the server-owned attempt subset."""
    correct_count = sum(data.answers[question.id] == question.answer for question in questions)
    total = len(questions)
    score = (correct_count * 100 + total // 2) // total
    return Submission(
        attempt_id=attempt.id,
        display_name=data.display_name,
        mode=attempt.mode,
        score=score,
        correct_count=correct_count,
        total=total,
    )


def persist_answer_snapshots(
    session: Session, submission: Submission, questions: list[Question], answers: dict[int, str]
) -> None:
    """Write historical snapshots before later question edits can alter their meaning."""
    for question in questions:
        selected = answers[question.id]
        session.add(
            SubmissionAnswer(
                submission_id=submission.id,
                question_id=question.id,
                question_text=question.text,
                image_url=question.image_url,
                options=[
                    question.option_a,
                    question.option_b,
                    question.option_c,
                    question.option_d,
                ],
                selected=selected,
                correct_answer=question.answer,
                explanation=question.explanation,
                is_correct=selected == question.answer,
            )
        )


def submission_for_attempt(session: Session, attempt_id: int) -> Submission | None:
    """Find the sole score row that makes a retry idempotent."""
    return session.scalar(select(Submission).where(Submission.attempt_id == attempt_id))


def stored_result(session: Session, submission: Submission) -> SubmissionResult:
    """Read persisted snapshots rather than recalculating a historical result."""
    answers = session.scalars(
        select(SubmissionAnswer)
        .where(SubmissionAnswer.submission_id == submission.id)
        .order_by(SubmissionAnswer.id)
    ).all()
    return submission_result(submission, answers)
