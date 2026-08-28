"""Drain durable question/note publication tasks for the single-host deployment."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import load_settings
from app.database import Database
from app.services import sync


def main() -> int:
    parser = argparse.ArgumentParser(description="publish the MikanQuiz JSON sync outbox")
    parser.add_argument("--outbox-id", type=int, help="retry one specific outbox row")
    parser.add_argument("--drain", action="store_true", help="process all currently eligible rows")
    args = parser.parse_args()
    settings = load_settings()
    database = Database(settings.database_url)
    if args.outbox_id is not None:
        sync.retry_outbox(database, args.outbox_id)
        sync.run_once(database, settings, args.outbox_id)
        return 0
    if args.drain:
        for _ in range(100):
            if not sync.run_once(database, settings):
                break
        return 0
    sync.run_once(database, settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
