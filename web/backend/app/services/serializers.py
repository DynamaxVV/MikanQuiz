"""Explicit model-to-schema conversion helpers."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FontOption, OptionGroup, Question, QuizSettings, Submission, SubmissionAnswer, as_utc
from app.schemas import FontOptionResponse, OptionGroupResponse, PublicQuestion, QuestionResponse, SettingsResponse, SubmissionDetail, SubmissionListItem, SubmissionResult


def catalogue(session: Session, difficulty: int | None = None) -> list[OptionGroupResponse]:
    """Build grouped options, optionally hiding fonts locked above a star level."""
    groups = session.scalars(select(OptionGroup).order_by(OptionGroup.sort_order, OptionGroup.id)).all()
    options = session.scalars(select(FontOption).order_by(FontOption.sort_order, FontOption.id)).all()
    by_group: dict[int, list[FontOptionResponse]] = {group.id: [] for group in groups}
    for option in options:
        if difficulty is None or option.minimum_difficulty <= difficulty:
            by_group[option.group_id].append(FontOptionResponse(id=option.id, name=option.name, font_url=option.font_url, minimum_difficulty=option.minimum_difficulty, sort_order=option.sort_order))
    return [OptionGroupResponse(id=group.id, name=group.name, sort_order=group.sort_order, options=by_group[group.id]) for group in groups if by_group[group.id] or difficulty is None]


def _option_response(option: FontOption) -> FontOptionResponse:
    return FontOptionResponse(id=option.id, name=option.name, font_url=option.font_url, minimum_difficulty=option.minimum_difficulty, sort_order=option.sort_order)


def public_question(session: Session, question: Question) -> PublicQuestion:
    """Serialize only information safe to disclose before an answer is submitted."""
    return PublicQuestion(id=question.id, text=question.text, image_url=question.image_url, difficulty=question.difficulty, option_groups=catalogue(session, question.difficulty))


def admin_question(session: Session, question: Question) -> QuestionResponse:
    """Serialize the answer and its owning group for the authenticated editor."""
    option = session.get(FontOption, question.correct_option_id) if question.correct_option_id else None
    group = session.get(OptionGroup, option.group_id) if option else None
    if option is None or group is None:
        return QuestionResponse(id=question.id, text=question.text, image_url=question.image_url, difficulty=question.difficulty, correct_option_id=None, correct_option=None, correct_group=None, configuration_error="正确字体已被删除，请重新选择后保存题目", answer=None, explanation=question.explanation, created_at=as_utc(question.created_at), updated_at=as_utc(question.updated_at))
    return QuestionResponse(id=question.id, text=question.text, image_url=question.image_url, difficulty=question.difficulty, correct_option_id=option.id, correct_option=_option_response(option), correct_group=OptionGroupResponse(id=group.id, name=group.name, sort_order=group.sort_order, options=[]), answer=option.name, explanation=question.explanation, created_at=as_utc(question.created_at), updated_at=as_utc(question.updated_at))


def settings_response(settings: QuizSettings) -> SettingsResponse:
    return SettingsResponse(question_count=settings.question_count, modes=settings.modes, font_presets=settings.font_presets)


def submission_detail(answer: SubmissionAnswer) -> SubmissionDetail:
    """Read both newly structured snapshots and preserved legacy A-D snapshots."""
    return SubmissionDetail(question_id=answer.question_id, question_text=answer.question_text, image_url=answer.image_url, options=answer.options, option_groups=[OptionGroupResponse.model_validate(group) for group in answer.option_groups] if answer.option_groups else None, selected=answer.selected, correct_answer=answer.correct_answer, selected_option_id=answer.selected_option_id, correct_option_id=answer.correct_option_id, explanation=answer.explanation, is_correct=answer.is_correct)


def submission_result(submission: Submission, answers: list[SubmissionAnswer]) -> SubmissionResult:
    return SubmissionResult(submission_id=submission.id, display_name=submission.display_name, mode=submission.mode, score=submission.score, correct_count=submission.correct_count, total=submission.total, submitted_at=as_utc(submission.submitted_at), details=[submission_detail(answer) for answer in answers])


def submission_list_item(submission: Submission) -> SubmissionListItem:
    return SubmissionListItem(id=submission.id, display_name=submission.display_name, mode=submission.mode, score=submission.score, correct_count=submission.correct_count, total=submission.total, submitted_at=as_utc(submission.submitted_at))
