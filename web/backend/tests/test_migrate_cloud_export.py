"""Safety checks for one-time cloud-export history migration."""

import importlib.util
from pathlib import Path

import pytest

from app.database import Database
from app.models import Question, Submission, SubmissionAnswer


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "migrate_cloud_export.py"
SPEC = importlib.util.spec_from_file_location("cloud_export_migration", SCRIPT_PATH)
assert SPEC and SPEC.loader
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


def current_question() -> Question:
    """Build a deliberately changed current question to detect unsafe inference."""
    return Question(
        legacy_id="legacy-question",
        text="当前题干",
        image_url="https://pan.yurucamp.cn/current.png",
        difficulty=1,
        option_a="当前甲",
        option_b="当前乙",
        option_c="当前丙",
        option_d="当前丁",
        answer="A",
        explanation="当前解析",
    )


def exported_submission() -> dict:
    """Return a verified historical snapshot whose answer differs from current data."""
    return {
        "displayName": "旧用户",
        "mode": "beginner",
        "score": 100,
        "correctCount": 1,
        "total": 1,
        "submittedAt": "2026-07-20T10:00:00Z",
        "answers": [
            {
                "questionId": "legacy-question",
                "selected": "B",
                "correctAnswer": "B",
                "isCorrect": True,
                "questionText": "旧题干",
                "imageUrl": "https://pan.yurucamp.cn/old.png",
                "options": ["旧甲", "旧乙", "旧丙", "旧丁"],
                "explanation": "旧解析",
            }
        ],
    }


def test_history_import_uses_verified_export_snapshot_not_current_question(
    database: Database,
) -> None:
    """Changed current answer and text must not alter a historical export snapshot."""
    with database.sessions() as session:
        question = current_question()
        session.add(question)
        session.flush()
        migration.import_submissions(
            session, [exported_submission()], {"legacy-question": question}
        )
        session.commit()
        submission = session.query(Submission).one()
        answer = session.query(SubmissionAnswer).one()
    assert (submission.score, submission.correct_count, submission.total) == (100, 1, 1)
    assert (answer.selected, answer.correct_answer, answer.is_correct) == ("B", "B", True)
    assert answer.question_text == "旧题干"
    assert answer.image_url == "https://pan.yurucamp.cn/old.png"
    assert answer.options == ["旧甲", "旧乙", "旧丙", "旧丁"]
    assert answer.explanation == "旧解析"


def test_history_import_rejects_export_without_complete_snapshot() -> None:
    """Old selected/isCorrect-only exports fail instead of consulting current questions."""
    record = exported_submission()
    item = record["answers"][0]
    for key in ("correctAnswer", "questionText", "options", "explanation"):
        item.pop(key)
    with pytest.raises(ValueError, match="缺少历史快照字段"):
        migration.verified_historical_answers(record, {"legacy-question": current_question()}, 1)
