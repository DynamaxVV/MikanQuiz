"""Anonymous attempt selection, snapshot grading and idempotent submission."""

from datetime import timedelta
import random
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Question, QuizAttempt, Submission, SubmissionAnswer, as_utc, utc_now
from app.schemas import AttemptSubmit, PublicQuestion
from app.security import hash_token, new_token
from app.services.questions import get_settings
from app.services.serializers import catalogue, public_question, submission_result


class RandomSource(Protocol):
    def random(self) -> float: ...


def create_attempt(session: Session, mode: str, random_source: RandomSource | None = None) -> tuple[str, QuizAttempt, list[PublicQuestion]]:
    settings = get_settings(session)
    weights = settings.modes[mode]
    effective_difficulty = max(i + 1 for i, w in enumerate(weights) if w > 0) if any(w > 0 for w in weights) else 1
    selected = select_questions(session.scalars(select(Question)).all(), settings.question_count, weights, random_source)
    if any(question.correct_option_id is None for question in selected):
        raise ApiError(409, "QUESTION_FONT_MISSING", "题库有题目的正确字体已被删除，请管理员修复后再开始练习")
    snapshots = []
    for question in selected:
        snapshot = public_question(session, question, effective_difficulty).model_dump(mode="json")
        snapshot["correct_option_id"] = question.correct_option_id
        snapshot["explanation"] = question.explanation
        snapshots.append(snapshot)
    token = new_token()
    attempt = QuizAttempt(token_hash=hash_token(token), mode=mode, question_ids=[item.id for item in selected], question_snapshots=snapshots, expires_at=utc_now() + timedelta(hours=24))
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return token, attempt, [_public_snapshot(item) for item in snapshots]


def select_questions(questions: list[Question], count: int, weights: list[int], random_source: RandomSource | None = None) -> list[Question]:
    eligible = [question for question in questions if weights[question.difficulty - 1] > 0]
    if not eligible:
        raise ApiError(409, "QUIZ_NOT_ENOUGH_QUESTIONS", "当前难度没有可用题目，请录入符合该难度权重的题目或调整出题策略")
    source = random_source or random.SystemRandom()
    return [_weighted_pop(eligible, weights, source) for _ in range(min(count, len(eligible)))]


def _weighted_pop(candidates: list[Question], weights: list[int], random_source: RandomSource) -> Question:
    cursor = random_source.random() * sum(weights[item.difficulty - 1] for item in candidates)
    for index, question in enumerate(candidates):
        cursor -= weights[question.difficulty - 1]
        if cursor < 0:
            return candidates.pop(index)
    return candidates.pop()


def current_attempt(session: Session, token: str) -> tuple[QuizAttempt, list[PublicQuestion]]:
    attempt = get_attempt(session, token)
    if attempt.submitted_at is not None:
        raise ApiError(409, "ATTEMPT_ALREADY_SUBMITTED", "本次答题已经提交")
    ensure_unexpired(attempt)
    return attempt, [_public_snapshot(item) for item in attempt.question_snapshots]


def _public_snapshot(snapshot: dict) -> PublicQuestion:
    """Strip server-only answer fields before an attempt reaches a client."""
    return PublicQuestion.model_validate({key: snapshot[key] for key in ("id", "text", "image_url", "difficulty", "option_groups")})


def get_attempt(session: Session, token: str) -> QuizAttempt:
    if not token:
        raise ApiError(401, "ATTEMPT_TOKEN_REQUIRED", "缺少答题会话")
    attempt = session.scalar(select(QuizAttempt).where(QuizAttempt.token_hash == hash_token(token)))
    if attempt is None:
        raise ApiError(404, "ATTEMPT_NOT_FOUND", "答题会话不存在")
    return attempt


def ensure_unexpired(attempt: QuizAttempt) -> None:
    if as_utc(attempt.expires_at) <= utc_now():
        raise ApiError(410, "ATTEMPT_EXPIRED", "本次答题已过期，请重新开始")


def submit_attempt(session: Session, token: str, data: AttemptSubmit):
    attempt = get_attempt(session, token)
    existing = submission_for_attempt(session, attempt.id)
    if existing is not None:
        return stored_result(session, existing)
    ensure_unexpired(attempt)
    snapshots = {item["id"]: item for item in attempt.question_snapshots}
    validate_answers(data.answers, snapshots)
    correct_count = sum(data.answers[question_id] == snapshots[question_id]["correct_option_id"] for question_id in snapshots)
    total = len(snapshots)
    submission = Submission(attempt_id=attempt.id, display_name=data.display_name, mode=attempt.mode, score=(correct_count * 100 + total // 2) // total, correct_count=correct_count, total=total)
    session.add(submission)
    session.flush()
    for question_id, snapshot in snapshots.items():
        selected = data.answers[question_id]
        correct = snapshot["correct_option_id"]
        groups = snapshot["option_groups"]
        session.add(SubmissionAnswer(submission_id=submission.id, question_id=question_id, question_text=snapshot["text"], difficulty=snapshot.get("difficulty", 1), image_url=snapshot.get("image_url"), options=[], option_groups=groups, selected=str(selected), correct_answer=str(correct), selected_option_id=selected, correct_option_id=correct, explanation=snapshot["explanation"], is_correct=selected == correct))
    attempt.submitted_at = utc_now()
    session.commit()
    return stored_result(session, submission)


def validate_answers(answers: dict[int, int], snapshots: dict[int, dict]) -> None:
    if set(answers) != set(snapshots):
        raise ApiError(422, "INVALID_ANSWERS", "答案必须完整且只能包含本次题目")
    for question_id, selected in answers.items():
        visible = {item["id"] for group in snapshots[question_id]["option_groups"] for item in group["options"]}
        if selected not in visible:
            raise ApiError(422, "INVALID_ANSWERS", "答案不属于该题可选字体")


def submission_for_attempt(session: Session, attempt_id: int) -> Submission | None:
    return session.scalar(select(Submission).where(Submission.attempt_id == attempt_id))


def stored_result(session: Session, submission: Submission):
    answers = session.scalars(select(SubmissionAnswer).where(SubmissionAnswer.submission_id == submission.id).order_by(SubmissionAnswer.id)).all()
    return submission_result(submission, answers)
