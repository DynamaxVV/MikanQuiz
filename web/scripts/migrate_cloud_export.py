"""Validate and import a one-time WeChat cloud export into the standalone schema."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Database
from app.models import FontOption, OptionGroup, Question, QuizAttempt, Submission, SubmissionAnswer
from app.schemas import SettingsResponse
from app.security import hash_token, new_token
from app.services.questions import get_settings


def build_parser() -> argparse.ArgumentParser:
    """Build a strict one-time import CLI without making any external writes by default."""
    parser = argparse.ArgumentParser(description="导入微信云开发题库导出 JSON")
    parser.add_argument("--questions", required=True, type=Path)
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--submissions", type=Path)
    parser.add_argument("--image-mapping", required=True, type=Path)
    parser.add_argument("--database-url", default=os.getenv("QUIZ_DATABASE_URL"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-images", action="store_true")
    parser.add_argument("--image-host", action="append", default=["pan.yurucamp.cn"])
    return parser


def read_records(path: Path) -> list[dict[str, Any]]:
    """Read list-shaped cloud export JSON, including common `data` wrappers."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("data", raw.get("records", [raw]))
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ValueError(f"{path} 必须是对象数组或包含 data 数组")
    return raw


def read_mapping(path: Path) -> dict[str, str]:
    """Read an image File ID-to-HTTPS URL mapping in object or record-list form."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        return {
            str(item["old_image_file_id"]): str(item["new_image_url"])
            for item in raw
            if isinstance(item, dict)
        }
    raise ValueError("图片映射必须是对象或记录数组")


def resolve_image_url(
    record: dict[str, Any], mapping: dict[str, str], hosts: list[str]
) -> str | None:
    """Require one mapped HTTPS URL for every legacy cloud image reference."""
    legacy_id = str(record.get("imageFileID") or "").strip()
    if not legacy_id:
        return None
    url = mapping.get(legacy_id)
    if not url:
        raise ValueError(f"题目 {record.get('_id', '<unknown>')} 缺少图片映射")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise ValueError(f"图片 URL 非 HTTPS 或不在允许图床：{url}")
    return url


def legacy_question_values(record: dict[str, Any], mapping: dict[str, str], hosts: list[str]) -> tuple[str, str | None, int, str, list[str]]:
    """Read a legacy question without retaining its fixed option representation."""
    answer = str(record.get("answer") or "")
    explanation = record.get("explanation") or record.get("explanations", {}).get(answer)
    options = [str(item).strip() for item in record.get("options", [])]
    if len(options) != 4 or any(not item for item in options) or answer not in "ABCD" or not explanation:
        raise ValueError("旧题目格式不正确")
    return str(record.get("text", "")), resolve_image_url(record, mapping, hosts), int(record.get("difficulty")), str(explanation), options


def verify_image(url: str, hosts: list[str]) -> None:
    """Check a mapped image response without fetching it through the API process."""
    request = Request(url, method="HEAD", headers={"User-Agent": "quiz-migration-check"})
    with urlopen(request, timeout=10) as response:  # nosec B310: host allowlist is checked
        final = urlparse(response.geturl())
        if final.scheme != "https" or final.hostname not in hosts:
            raise ValueError(f"图片重定向离开允许图床：{url}")
        if not response.headers.get_content_type().startswith("image/"):
            raise ValueError(f"图片不是 image/* 响应：{url}")


def import_questions(
    session: Any, records: list[dict[str, Any]], mapping: dict[str, str], hosts: list[str]
) -> dict[str, Question]:
    """Upsert all legacy questions by their cloud `_id` for auditable linkage."""
    imported: dict[str, Question] = {}
    for record in records:
        legacy_id = str(record.get("_id") or "").strip()
        if not legacy_id:
            raise ValueError("题目导出缺少 _id")
        text, image_url, difficulty, explanation, options = legacy_question_values(record, mapping, hosts)
        question = session.query(Question).filter_by(legacy_id=legacy_id).one_or_none()
        if question is None:
            other = session.query(OptionGroup).filter_by(name="其他").one()
            option_by_name = {}
            for position, option_name in enumerate(options):
                option = session.query(FontOption).filter_by(group_id=other.id, name=option_name).one_or_none()
                if option is None:
                    option = FontOption(group_id=other.id, name=option_name, minimum_difficulty=1, sort_order=position)
                    session.add(option)
                    session.flush()
                option_by_name[option_name] = option
            correct_name = options[ord(str(record["answer"])) - ord("A")]
            question = Question(legacy_id=legacy_id, correct_option_id=option_by_name[correct_name].id)
            session.add(question)
        question.text, question.image_url, question.difficulty = text, image_url, difficulty
        question.explanation = explanation
        imported[legacy_id] = question
    session.flush()
    return imported


def import_settings(session: Any, path: Path | None) -> None:
    """Convert old camelCase settings and validate them before replacing the singleton."""
    if path is None:
        return
    records = read_records(path)
    if len(records) != 1:
        raise ValueError("设置导出必须恰好包含一个对象")
    record = records[0]
    validated = SettingsResponse(
        question_count=record.get("questionCount"),
        modes=record.get("modes"),
        font_presets=record.get("fontPresets", []),
    )
    settings = get_settings(session)
    settings.question_count = validated.question_count
    settings.modes = validated.modes
    settings.font_presets = validated.font_presets


def parse_submitted_at(value: Any) -> datetime:
    """Parse a required historical cloud timestamp without inventing one."""
    if value is None:
        raise ValueError("历史提交缺少 submittedAt，无法保留原始时间")
    if isinstance(value, dict):
        value = value.get("$date")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def import_submissions(
    session: Any, records: list[dict[str, Any]], questions: dict[str, Question]
) -> None:
    """Create historical submitted attempts and immutable answer snapshots from exports."""
    for index, record in enumerate(records, start=1):
        answers = verified_historical_answers(record, questions, index)
        saved_at = parse_submitted_at(record.get("submittedAt"))
        attempt = QuizAttempt(
            token_hash=hash_token(new_token()),
            mode=record.get("mode", "beginner"),
            question_ids=[question.id for question, _ in answers],
            created_at=saved_at,
            expires_at=saved_at,
            submitted_at=saved_at,
        )
        session.add(attempt)
        session.flush()
        write_submission(session, attempt, record, answers, saved_at)


def write_submission(
    session: Any,
    attempt: QuizAttempt,
    record: dict[str, Any],
    answers: list[tuple[Question, dict[str, Any]]],
    saved_at: datetime,
) -> None:
    """Persist export-verified history without reading current answer or parse fields."""
    submission = Submission(
        attempt_id=attempt.id,
        display_name=str(record.get("displayName") or "").strip()[:20],
        mode=attempt.mode,
        score=record["score"],
        correct_count=record["correctCount"],
        total=record["total"],
        submitted_at=saved_at,
    )
    session.add(submission)
    session.flush()
    for question, item in answers:
        session.add(
            SubmissionAnswer(
                submission_id=submission.id,
                question_id=question.id,
                question_text=item["question_text"],
                image_url=item["image_url"],
                options=item["options"],
                selected=item["selected"],
                correct_answer=item["correct_answer"],
                explanation=item["explanation"],
                is_correct=item["is_correct"],
            )
        )


def verified_historical_answers(
    record: dict[str, Any], questions: dict[str, Question], index: int
) -> list[tuple[Question, dict[str, Any]]]:
    """Verify that exported answer snapshots and aggregate values agree exactly."""
    items = record.get("answers")
    if not isinstance(items, list) or not items:
        raise ValueError(f"历史提交 {index} 缺少 answers，无法安全导入")
    answers = [historical_answer(item, questions, index) for item in items]
    if len({question.id for question, _ in answers}) != len(answers):
        raise ValueError(f"历史提交 {index} 包含重复题目")
    validate_historical_totals(record, answers, index)
    return answers


def historical_answer(
    item: Any, questions: dict[str, Question], submission_index: int
) -> tuple[Question, dict[str, Any]]:
    """Require a complete export snapshot instead of looking at current questions."""
    if not isinstance(item, dict):
        raise ValueError(f"历史提交 {submission_index} 的 answers 包含非对象")
    legacy_id = str(item.get("questionId") or "").strip()
    question = questions.get(legacy_id)
    if question is None:
        raise ValueError(f"历史提交 {submission_index} 引用了未导入题目")
    return question, history_snapshot(item, submission_index)


def history_snapshot(item: dict[str, Any], submission_index: int) -> dict[str, Any]:
    """Normalize supported export keys and reject missing historical evidence."""
    fields = {
        "selected": item.get("selected"),
        "correct_answer": item.get("correctAnswer", item.get("correct_answer")),
        "is_correct": item.get("isCorrect", item.get("is_correct")),
        "question_text": item.get("questionText", item.get("question_text")),
        "image_url": item.get("imageUrl", item.get("image_url")),
        "options": item.get("options"),
        "explanation": item.get("explanation"),
    }
    required = [
        "selected",
        "correct_answer",
        "is_correct",
        "question_text",
        "options",
        "explanation",
    ]
    missing = [name for name in required if fields[name] is None]
    if missing:
        raise ValueError(f"历史提交 {submission_index} 缺少历史快照字段：{'、'.join(missing)}")
    return validate_history_snapshot(fields, submission_index)


def validate_history_snapshot(
    snapshot: dict[str, Any], submission_index: int
) -> dict[str, Any]:
    """Check answer choices, snapshot shape and self-consistent correctness evidence."""
    selected, correct = str(snapshot["selected"]), str(snapshot["correct_answer"])
    if selected not in {"A", "B", "C", "D"} or correct not in {"A", "B", "C", "D"}:
        raise ValueError(f"历史提交 {submission_index} 包含非法选项")
    if not isinstance(snapshot["is_correct"], bool) or snapshot["is_correct"] != (selected == correct):
        raise ValueError(f"历史提交 {submission_index} 的 isCorrect 与答案快照不一致")
    if not isinstance(snapshot["options"], list) or len(snapshot["options"]) != 4:
        raise ValueError(f"历史提交 {submission_index} 的选项快照必须恰好四项")
    options = [str(value).strip() for value in snapshot["options"]]
    if not all(options) or not str(snapshot["question_text"]).strip() or not str(snapshot["explanation"]).strip():
        raise ValueError(f"历史提交 {submission_index} 的题目快照不能为空")
    image_url = normalize_snapshot_image(snapshot["image_url"], submission_index)
    return {**snapshot, "selected": selected, "correct_answer": correct, "options": options, "image_url": image_url}


def normalize_snapshot_image(value: Any, submission_index: int) -> str | None:
    """Accept no historical image, but require HTTPS for a saved snapshot URL."""
    if value is None or not str(value).strip():
        return None
    image_url = str(value).strip()
    parsed = urlparse(image_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"历史提交 {submission_index} 的图片快照必须是 HTTPS URL")
    return image_url


def validate_historical_totals(
    record: dict[str, Any], answers: list[tuple[Question, dict[str, Any]]], index: int
) -> None:
    """Validate exported score fields against exported per-answer correctness only."""
    score, correct, total = record.get("score"), record.get("correctCount"), record.get("total")
    invalid = any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in (score, correct, total)
    )
    if invalid:
        raise ValueError(f"历史提交 {index} 缺少可验证的 score、correctCount 或 total")
    actual_correct = sum(snapshot["is_correct"] for _, snapshot in answers)
    expected_score = (actual_correct * 100 + len(answers) // 2) // len(answers)
    if (correct, total, score) != (actual_correct, len(answers), expected_score):
        raise ValueError(f"历史提交 {index} 的分数与答案快照不一致")


def main() -> int:
    """Validate all source data before committing an optional one-time import."""
    args = build_parser().parse_args()
    if not args.database_url:
        raise SystemExit("需要 --database-url 或 QUIZ_DATABASE_URL")
    records, mapping = read_records(args.questions), read_mapping(args.image_mapping)
    payloads = [question_payload(record, mapping, args.image_host) for record in records]
    if args.verify_images:
        for payload in payloads:
            if payload.image_url:
                verify_image(payload.image_url, args.image_host)
    submissions = read_records(args.submissions) if args.submissions else []
    if args.dry_run:
        print(f"校验通过：题目 {len(payloads)}，历史提交 {len(submissions)}")
        return 0
    database = Database(args.database_url)
    with database.sessions() as session:
        try:
            imported = import_questions(session, records, mapping, args.image_host)
            import_settings(session, args.settings)
            import_submissions(session, submissions, imported)
            session.commit()
        except Exception:
            session.rollback()
            raise
    print(f"导入完成：题目 {len(records)}，历史提交 {len(submissions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
