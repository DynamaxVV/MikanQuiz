"""Anonymous attempt selection, snapshot grading and idempotent submission."""

from collections import Counter, defaultdict
from collections.abc import Sequence
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


MODE_OPTION_DIFFICULTY = {
    "beginner": 1,
    "proficient": 2,
    "challenge": 3,
}

RECENT_ATTEMPT_LIMIT = 3
FONT_REPEAT_SOFT_LIMIT = 2
RECENT_QUESTION_PENALTIES = (0.35, 0.55, 0.75)
RECENT_QUESTION_REPEAT_DECAY = 0.8


class RandomSource(Protocol):
    def random(self) -> float: ...


def create_attempt(session: Session, mode: str, random_source: RandomSource | None = None) -> tuple[str, QuizAttempt, list[PublicQuestion]]:
    settings = get_settings(session)
    weights = settings.modes[mode]
    questions = session.scalars(select(Question)).all()
    recent_attempts = session.scalars(
        select(QuizAttempt)
        .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id.desc())
        .limit(RECENT_ATTEMPT_LIMIT)
    ).all()
    selected = select_questions(
        questions,
        settings.question_count,
        weights,
        random_source,
        recent_attempts=recent_attempts,
    )
    if any(question.correct_option_id is None for question in selected):
        raise ApiError(409, "QUESTION_FONT_MISSING", "题库有题目的正确字体已被删除，请管理员修复后再开始练习")
    option_difficulty = MODE_OPTION_DIFFICULTY[mode]
    snapshots = []
    for question in selected:
        snapshot = public_question(session, question, mode_difficulty=option_difficulty).model_dump(mode="json")
        snapshot["correct_option_id"] = question.correct_option_id
        snapshot["explanation"] = question.explanation
        snapshots.append(snapshot)
    token = new_token()
    attempt = QuizAttempt(token_hash=hash_token(token), mode=mode, question_ids=[item.id for item in selected], question_snapshots=snapshots, expires_at=utc_now() + timedelta(hours=24))
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return token, attempt, [_public_snapshot(item) for item in snapshots]


def select_questions(
    questions: list[Question],
    count: int,
    weights: list[int],
    random_source: RandomSource | None = None,
    recent_attempts: Sequence[QuizAttempt] | None = None,
) -> list[Question]:
    """Select a quota-balanced, font-diverse question set without replacement.

    The configured star values are treated as relative quota ratios. Recent
    attempts influence only the soft ordering of fonts and questions; they
    never make a question ineligible.
    """
    eligible = [question for question in questions if weights[question.difficulty - 1] > 0]
    if not eligible:
        raise ApiError(409, "QUIZ_NOT_ENOUGH_QUESTIONS", "当前难度没有可用题目，请录入符合该难度权重的题目或调整出题策略")
    source = random_source or random.SystemRandom()
    candidates_by_difficulty: dict[int, list[Question]] = {difficulty: [] for difficulty in (1, 2, 3)}
    for question in eligible:
        candidates_by_difficulty[question.difficulty].append(question)
    quotas = _difficulty_quotas(candidates_by_difficulty, count, weights)
    history = _selection_history(questions, recent_attempts)
    selected: list[Question] = []
    selected_font_counts: Counter[object] = Counter()

    for difficulty in (1, 2, 3):
        candidates = candidates_by_difficulty[difficulty]
        for _ in range(quotas[difficulty]):
            question = _select_from_difficulty(candidates, history, selected_font_counts, source)
            selected.append(question)

    _shuffle(selected, source)
    return selected


def _difficulty_quotas(
    candidates_by_difficulty: dict[int, list[Question]], count: int, weights: list[int]
) -> dict[int, int]:
    """Convert relative star ratios into integer per-attempt quotas."""
    available = {
        difficulty: len(candidates_by_difficulty[difficulty])
        for difficulty in (1, 2, 3)
    }
    active = [
        difficulty
        for difficulty in (1, 2, 3)
        if weights[difficulty - 1] > 0 and available[difficulty] > 0
    ]
    quotas = {difficulty: 0 for difficulty in (1, 2, 3)}
    if not active:
        return quotas

    draw_count = min(max(count, 0), sum(available[difficulty] for difficulty in active))
    weight_total = sum(weights[difficulty - 1] for difficulty in active)
    raw = {
        difficulty: draw_count * weights[difficulty - 1] / weight_total
        for difficulty in active
    }
    for difficulty in active:
        quotas[difficulty] = min(int(raw[difficulty]), available[difficulty])

    while sum(quotas.values()) < draw_count:
        remaining = [
            difficulty
            for difficulty in active
            if quotas[difficulty] < available[difficulty]
        ]
        if not remaining:
            break
        difficulty = max(
            remaining,
            key=lambda item: (raw[item] - quotas[item], weights[item - 1], -item),
        )
        quotas[difficulty] += 1
    return quotas


class _SelectionHistory:
    def __init__(self) -> None:
        self.question_counts: Counter[int] = Counter()
        self.question_ages: dict[int, int] = {}
        self.font_counts: Counter[object] = Counter()


def _selection_history(
    questions: Sequence[Question], recent_attempts: Sequence[QuizAttempt] | None
) -> _SelectionHistory:
    """Build exposure counts from the newest three attempts, newest first."""
    history = _SelectionHistory()
    questions_by_id = {question.id: question for question in questions}
    for age, attempt in enumerate((recent_attempts or ())[:RECENT_ATTEMPT_LIMIT]):
        for question_id in attempt.question_ids or []:
            question = questions_by_id.get(question_id)
            if question is None:
                continue
            history.question_counts[question_id] += 1
            history.question_ages[question_id] = min(
                age, history.question_ages.get(question_id, age)
            )
            history.font_counts[_font_key(question)] += 1
    return history


def _font_key(question: Question) -> object:
    """Use the correct font option as the font identity for balancing."""
    return question.correct_option_id if question.correct_option_id is not None else ("missing", question.id)


def _select_from_difficulty(
    candidates: list[Question],
    history: _SelectionHistory,
    selected_font_counts: Counter[object],
    random_source: RandomSource,
) -> Question:
    by_font: dict[object, list[Question]] = defaultdict(list)
    for question in candidates:
        by_font[_font_key(question)].append(question)

    preferred_fonts = [
        font
        for font in by_font
        if selected_font_counts[font] < FONT_REPEAT_SOFT_LIMIT
    ]
    fonts = preferred_fonts or list(by_font)
    font_weights = [
        _font_selection_weight(font, history, selected_font_counts)
        for font in fonts
    ]
    font = _weighted_choice(fonts, font_weights, random_source)
    font_candidates = by_font[font]
    question_weights = [
        _question_selection_weight(question.id, history)
        for question in font_candidates
    ]
    question = _weighted_choice(font_candidates, question_weights, random_source)
    candidates.remove(question)
    selected_font_counts[font] += 1
    return question


def _font_selection_weight(
    font: object, history: _SelectionHistory, selected_font_counts: Counter[object]
) -> float:
    """Favor fonts seen less often recently and earlier in this attempt."""
    return 1.0 / (
        (1 + history.font_counts.get(font, 0))
        * (1 + selected_font_counts.get(font, 0))
    )


def _question_selection_weight(question_id: int, history: _SelectionHistory) -> float:
    """Lower, but never zero, the weight of recently shown question IDs."""
    count = history.question_counts.get(question_id, 0)
    if count == 0:
        return 1.0
    age = min(history.question_ages.get(question_id, len(RECENT_QUESTION_PENALTIES) - 1), len(RECENT_QUESTION_PENALTIES) - 1)
    return RECENT_QUESTION_PENALTIES[age] * RECENT_QUESTION_REPEAT_DECAY ** (count - 1)


def _weighted_choice(items: Sequence[object], weights: Sequence[float], random_source: RandomSource) -> object:
    return items[_weighted_index(weights, random_source)]


def _weighted_index(weights: Sequence[float], random_source: RandomSource) -> int:
    total = sum(weights)
    if total <= 0:
        return len(weights) - 1
    cursor = random_source.random() * total
    for index, weight in enumerate(weights):
        cursor -= weight
        if cursor < 0:
            return index
    return len(weights) - 1


def _shuffle(items: list[Question], random_source: RandomSource) -> None:
    for right in range(len(items) - 1, 0, -1):
        left = min(int(random_source.random() * (right + 1)), right)
        items[left], items[right] = items[right], items[left]


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
