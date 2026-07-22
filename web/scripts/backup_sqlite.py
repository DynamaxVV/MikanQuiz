"""Create, validate, checksum and optionally upload an online SQLite backup."""

import argparse
from datetime import date, datetime, timedelta
import gzip
from hashlib import sha256
from pathlib import Path
import shutil
import sqlite3
import subprocess


def build_parser() -> argparse.ArgumentParser:
    """Build a backup command that does not depend on the running API process."""
    parser = argparse.ArgumentParser(description="备份 SQLite 题库")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--oss-target", help="例如 oss://bucket/quiz-backups/")
    parser.add_argument("--ossutil", default="ossutil")
    return parser


def backup_database(source: Path, destination: Path) -> Path:
    """Use SQLite's online backup API and verify integrity before compression."""
    if not source.is_file():
        raise ValueError(f"数据库不存在：{source}")
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    revision = schema_revision(source)
    raw = destination / f"quiz-{stamp}-{revision}.sqlite"
    with sqlite3.connect(source) as input_db, sqlite3.connect(raw) as output_db:
        input_db.backup(output_db)
    with sqlite3.connect(raw) as check_db:
        if check_db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("备份完整性检查失败")
    return raw


def schema_revision(source: Path) -> str:
    """Read the Alembic revision so each backup names its recoverable schema."""
    with sqlite3.connect(source) as connection:
        value = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    return "".join(character for character in str(value) if character.isalnum() or character == "_")


def compress_and_checksum(raw: Path) -> tuple[Path, Path]:
    """Compress a verified backup and produce a companion SHA-256 checksum file."""
    archive = raw.with_suffix(raw.suffix + ".gz")
    with raw.open("rb") as source, gzip.open(archive, "wb") as target:
        shutil.copyfileobj(source, target)
    digest = sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    raw.unlink()
    return archive, checksum


def upload_oss(ossutil: str, target: str, files: tuple[Path, Path]) -> None:
    """Upload both artifacts and fail the timer when the OSS client reports failure."""
    base = target.rstrip("/") + "/"
    for file in files:
        subprocess.run([ossutil, "cp", str(file), base + file.name], check=True)


def rotate_backups(destination: Path, keep_daily: int = 7, keep_weekly: int = 4) -> None:
    """Keep recent daily backups plus one recent archive per ISO week locally."""
    archives = sorted(destination.glob("quiz-*.sqlite.gz"), key=lambda item: item.name)
    cutoff = date.today() - timedelta(days=keep_daily - 1)
    weekly: dict[tuple[int, int], Path] = {}
    keep: set[Path] = set()
    for archive in reversed(archives):
        day = datetime.strptime(archive.name[5:13], "%Y%m%d").date()
        if day >= cutoff:
            keep.add(archive)
        weekly.setdefault(day.isocalendar()[:2], archive)
    keep.update(list(weekly.values())[:keep_weekly])
    for archive in archives:
        if archive not in keep:
            archive.unlink()
            archive.with_suffix(archive.suffix + ".sha256").unlink(missing_ok=True)


def main() -> int:
    """Run one consistent backup and optional OSS replication operation."""
    args = build_parser().parse_args()
    raw = backup_database(args.database, args.destination)
    files = compress_and_checksum(raw)
    if args.oss_target:
        upload_oss(args.ossutil, args.oss_target, files)
    rotate_backups(args.destination)
    print(files[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
