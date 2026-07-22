"""Remove only expired anonymous attempts that were never submitted."""

import argparse
import os
from pathlib import Path
import sys

from sqlalchemy import delete

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Database
from app.models import QuizAttempt, utc_now


def main() -> int:
    """Delete expired unfinished sessions while preserving all submission history."""
    parser = argparse.ArgumentParser(description="清理过期未提交答题会话")
    parser.add_argument("--database-url", default=os.getenv("QUIZ_DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("需要 --database-url 或 QUIZ_DATABASE_URL")
    database = Database(args.database_url)
    with database.sessions() as session:
        result = session.execute(
            delete(QuizAttempt).where(
                QuizAttempt.expires_at < utc_now(), QuizAttempt.submitted_at.is_(None)
            )
        )
        session.commit()
    print(f"已清理 {result.rowcount or 0} 个过期未提交会话")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
