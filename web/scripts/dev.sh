#!/bin/sh

set -eu

WEB_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BACKEND="$WEB_ROOT/backend"

if [ ! -x "$BACKEND/.venv/bin/uvicorn" ]; then
  echo "请先按 web/README.md 创建后端虚拟环境并安装依赖。" >&2
  exit 1
fi

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}

cd "$BACKEND"
"$BACKEND/.venv/bin/alembic" upgrade head
"$BACKEND/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
trap cleanup EXIT INT TERM

cd "$WEB_ROOT/frontend"
npm run dev
