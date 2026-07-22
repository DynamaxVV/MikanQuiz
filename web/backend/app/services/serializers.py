"""Explicit model-to-schema conversion helpers."""

from app.models import Question, QuizSettings, Submission, SubmissionAnswer, as_utc
from app.schemas import (
    PublicQuestion,
    QuestionResponse,
    SettingsResponse,
    SubmissionDetail,
    SubmissionListItem,
    SubmissionResult,
)


def question_options(question: Question) -> list[str]:
    """Return fixed option columns in their stable A-to-D order."""
    return [question.option_a, question.option_b, question.option_c, question.option_d]


def public_question(question: Question) -> PublicQuestion:
    """Serialize only information safe to disclose before an answer is submitted."""
    return PublicQuestion(
        id=question.id,
        text=question.text,
        image_url=question.image_url,
        difficulty=question.difficulty,
        options=question_options(question),
    )


def admin_question(question: Question) -> QuestionResponse:
    """Serialize an editable question for an authenticated administrator."""
    return QuestionResponse(
        id=question.id,
        text=question.text,
        image_url=question.image_url,
        difficulty=question.difficulty,
        options=question_options(question),
        answer=question.answer,
        explanation=question.explanation,
        created_at=as_utc(question.created_at),
        updated_at=as_utc(question.updated_at),
    )


def settings_response(settings: QuizSettings) -> SettingsResponse:
    """Serialize the singleton settings row through its full validator."""
    return SettingsResponse(
        question_count=settings.question_count,
        modes=settings.modes,
        font_presets=settings.font_presets,
    )


def submission_detail(answer: SubmissionAnswer) -> SubmissionDetail:
    """Serialize a stored historical answer snapshot."""
    return SubmissionDetail(
        question_id=answer.question_id,
        question_text=answer.question_text,
        image_url=answer.image_url,
        options=answer.options,
        selected=answer.selected,
        correct_answer=answer.correct_answer,
        explanation=answer.explanation,
        is_correct=answer.is_correct,
    )


def submission_result(
    submission: Submission, answers: list[SubmissionAnswer]
) -> SubmissionResult:
    """Build the stable result envelope used for an idempotent submit retry."""
    return SubmissionResult(
        submission_id=submission.id,
        display_name=submission.display_name,
        mode=submission.mode,
        score=submission.score,
        correct_count=submission.correct_count,
        total=submission.total,
        submitted_at=as_utc(submission.submitted_at),
        details=[submission_detail(answer) for answer in answers],
    )


def submission_list_item(submission: Submission) -> SubmissionListItem:
    """Build the compact admin submission-history table representation."""
    return SubmissionListItem(
        id=submission.id,
        display_name=submission.display_name,
        mode=submission.mode,
        score=submission.score,
        correct_count=submission.correct_count,
        total=submission.total,
        submitted_at=as_utc(submission.submitted_at),
    )

