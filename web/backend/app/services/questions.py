"""Question CRUD and singleton settings operations."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Question, QuizSettings
from app.schemas import (
    FontPresetsUpdate,
    QuestionPatch,
    QuestionWrite,
    SettingsResponse,
    StrategyUpdate,
)


DEFAULT_MODES = {
    "beginner": [65, 25, 10, 0, 0],
    "proficient": [15, 25, 30, 20, 10],
    "challenge": [0, 10, 20, 30, 40],
}


def get_settings(session: Session) -> QuizSettings:
    """Return the migration-seeded singleton settings row."""
    settings = session.get(QuizSettings, 1)
    if settings is None:
        raise ApiError(503, "SETTINGS_UNAVAILABLE", "题目设置尚未初始化")
    return settings


def create_question(session: Session, data: QuestionWrite) -> Question:
    """Create a fully validated fixed-four-option question."""
    question = Question(
        text=data.text,
        image_url=data.image_url,
        difficulty=data.difficulty,
        option_a=data.options[0],
        option_b=data.options[1],
        option_c=data.options[2],
        option_d=data.options[3],
        answer=data.answer,
        explanation=data.explanation,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


def get_question(session: Session, question_id: int) -> Question:
    """Load an editable question or return the stable not-found error."""
    question = session.get(Question, question_id)
    if question is None:
        raise ApiError(404, "QUESTION_NOT_FOUND", "题目不存在")
    return question


def update_question(
    session: Session, question: Question, patch: QuestionPatch
) -> Question:
    """Merge a partial patch and validate the complete final question once."""
    values = _question_values(question)
    values.update(patch.model_dump(exclude_unset=True))
    data = QuestionWrite.model_validate(values)
    _apply_question(question, data)
    session.commit()
    session.refresh(question)
    return question


def delete_question(session: Session, question: Question) -> None:
    """Delete a current question while leaving submission snapshots intact."""
    session.delete(question)
    session.commit()


def list_questions(
    session: Session,
    page: int,
    page_size: int,
    query: str | None,
    difficulties: list[int] | None,
) -> tuple[list[Question], int]:
    """Return a stable, bounded question page with optional filters."""
    statement = select(Question)
    count_statement = select(func.count()).select_from(Question)
    if query:
        statement = statement.where(Question.text.contains(query.strip()))
        count_statement = count_statement.where(Question.text.contains(query.strip()))
    if difficulties:
        statement = statement.where(Question.difficulty.in_(difficulties))
        count_statement = count_statement.where(Question.difficulty.in_(difficulties))
    total = int(session.scalar(count_statement))
    items = session.scalars(
        statement.order_by(Question.updated_at.desc(), Question.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total


def update_strategy(
    session: Session, data: StrategyUpdate, settings: QuizSettings
) -> QuizSettings:
    """Persist a fully validated weighted draw strategy."""
    validated = data.as_settings(settings.font_presets)
    settings.question_count = validated.question_count
    settings.modes = validated.modes
    session.commit()
    session.refresh(settings)
    return settings


def update_font_presets(
    session: Session, data: FontPresetsUpdate, settings: QuizSettings
) -> QuizSettings:
    """Validate and persist developer-configured option editing shortcuts."""
    payload = SettingsResponse(
        question_count=settings.question_count,
        modes=settings.modes,
        font_presets=data.font_presets,
    )
    settings.font_presets = payload.font_presets
    session.commit()
    session.refresh(settings)
    return settings


def _question_values(question: Question) -> dict[str, object]:
    """Make one complete validation payload from an existing model row."""
    return {
        "text": question.text,
        "image_url": question.image_url,
        "difficulty": question.difficulty,
        "options": [question.option_a, question.option_b, question.option_c, question.option_d],
        "answer": question.answer,
        "explanation": question.explanation,
    }


def _apply_question(question: Question, data: QuestionWrite) -> None:
    """Copy a validated question payload into its fixed storage columns."""
    question.text = data.text
    question.image_url = data.image_url
    question.difficulty = data.difficulty
    question.option_a, question.option_b, question.option_c, question.option_d = data.options
    question.answer = data.answer
    question.explanation = data.explanation
