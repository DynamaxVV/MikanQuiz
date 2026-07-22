"""Server-only administrator account management commands."""

import argparse
import getpass
import sys

from app.config import load_settings
from app.database import Database
from app.services import admin as admin_service


def build_parser() -> argparse.ArgumentParser:
    """Build the intentionally small standard-library administrator CLI."""
    parser = argparse.ArgumentParser(description="管理砂糖字形课堂管理员账号")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("add", "password", "disable", "enable", "list"):
        child = commands.add_parser(command)
        if command != "list":
            child.add_argument("username")
        if command in {"add", "password"}:
            child.add_argument("--password", help="仅用于受控自动化；日常请省略后交互输入")
    return parser


def read_password(value: str | None) -> str:
    """Read and confirm a password unless an explicit automation value was supplied."""
    if value is not None:
        return value
    password = getpass.getpass("密码: ")
    if password != getpass.getpass("再次输入密码: "):
        raise ValueError("两次输入的密码不一致")
    return password


def run_command(args: argparse.Namespace) -> str:
    """Perform one account operation in a short synchronous database session."""
    database = Database(load_settings().database_url)
    with database.sessions() as session:
        if args.command == "list":
            admins = admin_service.list_admins(session)
            return "\n".join(
                f"{admin.username}\t{'启用' if admin.is_active else '已停用'}"
                for admin in admins
            ) or "暂无管理员账号"
        if args.command == "add":
            admin_service.add_admin(session, args.username, read_password(args.password))
            return "管理员账号已创建"
        if args.command == "password":
            admin_service.change_password(session, args.username, read_password(args.password))
            return "管理员密码已更新，现有会话已撤销"
        admin_service.set_admin_active(session, args.username, args.command == "enable")
        return "管理员账号已启用" if args.command == "enable" else "管理员账号已停用"


def main() -> int:
    """Run the CLI, returning a nonzero code for safe operator-visible failures."""
    args = build_parser().parse_args()
    try:
        print(run_command(args))
    except ValueError as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
