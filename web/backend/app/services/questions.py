"""Question CRUD, option catalogue and singleton settings operations."""

from sqlalchemy import func, select, asc, desc
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import FontOption, OptionGroup, Question, QuizSettings
from app.schemas import (
    FontOptionWrite,
    OptionCatalogUpdate,
    QuestionPatch,
    QuestionWrite,
    SettingsResponse,
    StrategyUpdate,
)


DEFAULT_MODES = {
    "beginner": [90, 10, 0],
    "proficient": [40, 40, 20],
    "challenge": [10, 40, 50],
}


def get_settings(session: Session) -> QuizSettings:
    """Return the migration-seeded singleton settings row."""
    settings = session.get(QuizSettings, 1)
    if settings is None:
        raise ApiError(503, "SETTINGS_UNAVAILABLE", "题目设置尚未初始化")
    return settings


def option_groups(session: Session) -> list[OptionGroup]:
    """Read the catalogue in the same stable order used by all clients."""
    return session.scalars(select(OptionGroup).order_by(OptionGroup.sort_order, OptionGroup.id)).all()


def option_for_question(session: Session, option_id: int, difficulty: int) -> FontOption:
    """Validate that a selected answer remains available at the question's star level."""
    option = session.get(FontOption, option_id)
    if option is None:
        raise ApiError(422, "FONT_OPTION_NOT_FOUND", "请选择分区库中的字体")
    if option.minimum_difficulty > difficulty:
        raise ApiError(422, "FONT_OPTION_LOCKED", "正确字体的最低难度不能高于题目难度")
    return option


def create_question(session: Session, data: QuestionWrite) -> Question:
    """Create a validated question pointing at one reusable font option."""
    option_for_question(session, data.correct_option_id, data.difficulty)
    question = Question(
        text=data.text, image_url=data.image_url, difficulty=data.difficulty,
        correct_option_id=data.correct_option_id, explanation=data.explanation,
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


def update_question(session: Session, question: Question, patch: QuestionPatch) -> Question:
    """Merge a partial patch and validate the complete final question once."""
    values = _question_values(question)
    values.update(patch.model_dump(exclude_unset=True))
    data = QuestionWrite.model_validate(values)
    _apply_question(session, question, data)
    session.commit()
    session.refresh(question)
    return question


def delete_question(session: Session, question: Question) -> None:
    """Delete a current question while leaving submission snapshots intact."""
    session.delete(question)
    session.commit()


def list_questions(session: Session, page: int, page_size: int, query: str | None, difficulties: list[int] | None, sort_by: str = "updated_at", sort_order: str = "desc") -> tuple[list[Question], int]:
    """Return a stable, bounded question page with optional filters and sorting."""
    statement = select(Question)
    count_statement = select(func.count()).select_from(Question)
    if query:
        statement = statement.where(Question.text.contains(query.strip()))
        count_statement = count_statement.where(Question.text.contains(query.strip()))
    if difficulties:
        statement = statement.where(Question.difficulty.in_(difficulties))
        count_statement = count_statement.where(Question.difficulty.in_(difficulties))
    total = int(session.scalar(count_statement))
    sort_column = getattr(Question, sort_by, Question.updated_at)
    order_fn = desc if sort_order == "desc" else asc
    items = session.scalars(statement.order_by(order_fn(sort_column), Question.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def replace_option_catalog(session: Session, payload: OptionCatalogUpdate) -> list[OptionGroup]:
    """Replace the catalogue and mark questions for repair when an option is removed."""
    existing_groups = {item.id: item for item in option_groups(session)}
    existing_options = {item.id: item for item in session.scalars(select(FontOption)).all()}
    incoming_group_ids = {item.id for item in payload.groups if item.id is not None}
    incoming_option_ids = {item.id for group in payload.groups for item in group.options if item.id is not None}
    missing_group_ids = set(existing_groups) - incoming_group_ids
    nonempty_groups = [
        existing_groups[group_id].name
        for group_id in missing_group_ids
        if any(option.group_id == group_id for option in existing_options.values())
    ]
    if nonempty_groups:
        raise ApiError(409, "OPTION_GROUP_NOT_EMPTY", "请先清空分区内的字体，再删除分区")
    missing_options = set(existing_options) - incoming_option_ids
    for group_data in payload.groups:
        group = existing_groups.get(group_data.id) if group_data.id else None
        if group is None:
            group = OptionGroup(name=group_data.name.strip(), sort_order=group_data.sort_order)
            session.add(group)
            session.flush()
        else:
            group.name, group.sort_order = group_data.name.strip(), group_data.sort_order
        for option_data in group_data.options:
            _upsert_option(session, existing_options.get(option_data.id) if option_data.id else None, group.id, option_data)
    if missing_options:
        session.query(Question).filter(Question.correct_option_id.in_(missing_options)).update(
            {Question.correct_option_id: None}, synchronize_session=False
        )
    for option_id in missing_options:
        session.delete(existing_options[option_id])
    for group_id in missing_group_ids:
        session.delete(existing_groups[group_id])
    session.commit()
    return option_groups(session)


def _upsert_option(session: Session, option: FontOption | None, group_id: int, data: FontOptionWrite) -> None:
    """Create or update one option without inventing a second write abstraction."""
    if option is None:
        session.add(FontOption(group_id=group_id, name=data.name.strip(), font_url=data.font_url, minimum_difficulty=data.minimum_difficulty, sort_order=data.sort_order))
        return
    option.group_id = group_id
    option.name = data.name.strip()
    option.font_url = data.font_url
    option.minimum_difficulty = data.minimum_difficulty
    option.sort_order = data.sort_order


def update_strategy(session: Session, data: StrategyUpdate, settings: QuizSettings) -> QuizSettings:
    """Persist a fully validated weighted draw strategy."""
    validated = data.as_settings(settings.font_presets)
    settings.question_count, settings.modes = validated.question_count, validated.modes
    session.commit()
    session.refresh(settings)
    return settings


def _question_values(question: Question) -> dict[str, object]:
    return {"text": question.text, "image_url": question.image_url, "difficulty": question.difficulty, "correct_option_id": question.correct_option_id, "explanation": question.explanation}


def _apply_question(session: Session, question: Question, data: QuestionWrite) -> None:
    option_for_question(session, data.correct_option_id, data.difficulty)
    question.text, question.image_url, question.difficulty = data.text, data.image_url, data.difficulty
    question.correct_option_id, question.explanation = data.correct_option_id, data.explanation
