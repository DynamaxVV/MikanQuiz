#!/usr/bin/env bash
# Update the existing Ubuntu deployment described in deploy/README.md.
# Run as the ubuntu deployment user, not as root. Requires noninteractive sudo.
set -euo pipefail

REPO_DIR=/home/ubuntu/MikanQuiz
SRC_WEB_DIR=$REPO_DIR/web
PROD_DIR=/home/ubuntu/mikanquiz
PROD_WEB_DIR=$PROD_DIR/src/web
PROD_BACKEND_DIR=$PROD_WEB_DIR/backend
PROD_FRONTEND_DIR=$PROD_DIR/frontend
PROD_UPLOADER_DIR=$PROD_WEB_DIR/r2-uploader
PROD_VENV=$PROD_BACKEND_DIR/.venv
ENV_FILE=/etc/quiz/quiz-api.env
DATABASE_FILE=/srv/quiz/data/quiz.db
BACKUP_DIR=/srv/quiz/data/backups
API_SERVICE=quiz-api.service

phase=preflight
api_stopped=false
timer_state_file=$PROD_DIR/.deploy-paused-timers
trap 'echo "部署失败，阶段：${phase}。请检查上方错误与服务日志。" >&2; if [[ "$api_stopped" == true ]]; then echo "API 可能仍在维护状态；已暂停定时器记录在 ${timer_state_file}，修复后重跑完成恢复。不自动回退数据库。" >&2; fi' ERR

echo '=== 0. 检查现有部署 ==='
for command in git rsync npm curl flock; do
  command -v "$command" >/dev/null
done
[[ -d "$REPO_DIR/.git" && -d "$PROD_BACKEND_DIR" ]]
[[ -x "$PROD_VENV/bin/python" && -x "$PROD_VENV/bin/alembic" ]]
sudo -n test -f "$DATABASE_FILE"
sudo -n -u ubuntu -g root test -r "$DATABASE_FILE"
sudo -n -u ubuntu -g root test -w "$(dirname "$DATABASE_FILE")"
if ! sudo -n test -d "$BACKUP_DIR"; then
  sudo -n install -d -o ubuntu -g root -m 750 "$BACKUP_DIR"
fi
sudo -n -u ubuntu -g root test -w "$BACKUP_DIR"
sudo -n grep -qxF 'QUIZ_DATABASE_URL=sqlite:////srv/quiz/data/quiz.db' "$ENV_FILE"
sudo -n grep -qxF 'QUIZ_R2_PUBLIC_BASE_URL=https://pan.mikanquiz.xyz' "$ENV_FILE"
# Ensure this is also the environment file used by the actual API unit.
unit_environment=$(sudo -n systemctl show "$API_SERVICE" --property=EnvironmentFiles --value)
[[ "$unit_environment" == *"$ENV_FILE "* || "$unit_environment" == "$ENV_FILE" ]]
sudo -n nginx -t

exec 9>"$PROD_DIR/.deploy.lock"
flock -n 9 || { echo '已有部署正在执行。' >&2; exit 1; }
# A failed previous deployment may already have stopped these timers.
if [[ -f "$timer_state_file" ]]; then
  while IFS= read -r timer; do
    case "$timer" in
      quiz-sync.timer|quiz-cleanup.timer|quiz-backup.timer) : ;;
      *) echo "定时器恢复记录无效：$timer_state_file" >&2; exit 1 ;;
    esac
  done < "$timer_state_file"
fi
cd "$REPO_DIR"
if [[ -n "$(git status --porcelain)" ]]; then
  echo '仓库有本地改动。请先检查并保留自己的修改，再部署；不要 reset/clean。' >&2
  exit 1
fi
echo "更新前提交：$(git rev-parse --short HEAD)"

phase=pull
echo '=== 1. 拉取代码与预构建前端 ==='
git pull --ff-only
echo "本次提交：$(git rev-parse --short HEAD)"
[[ -s "$SRC_WEB_DIR/frontend/dist/index.html" ]]
[[ -f "$SRC_WEB_DIR/scripts/backup_sqlite.py" ]]

install_backend_deps=false
install_uploader_deps=false
if ! cmp -s "$SRC_WEB_DIR/backend/requirements.txt" "$PROD_BACKEND_DIR/requirements.txt"; then
  install_backend_deps=true
fi
if [[ ! -d "$PROD_UPLOADER_DIR/node_modules" ]] ||
   ! cmp -s "$SRC_WEB_DIR/r2-uploader/package.json" "$PROD_UPLOADER_DIR/package.json" ||
   ! cmp -s "$SRC_WEB_DIR/r2-uploader/package-lock.json" "$PROD_UPLOADER_DIR/package-lock.json"; then
  install_uploader_deps=true
fi

phase=stop-and-backup
echo '=== 2. 暂停写入并备份当前数据库 ==='
# Pause installed/active timers before stopping their workers. Do not install units.
for timer in quiz-sync.timer quiz-cleanup.timer quiz-backup.timer; do
  if sudo -n systemctl is-active --quiet "$timer"; then
    if [[ ! -f "$timer_state_file" ]] || ! grep -qxF "$timer" "$timer_state_file"; then
      printf '%s\n' "$timer" >> "$timer_state_file"
    fi
    sudo -n systemctl stop "$timer"
  fi
done
for worker in quiz-sync.service quiz-cleanup.service quiz-backup.service; do
  if sudo -n systemctl is-active --quiet "$worker"; then
    sudo -n systemctl stop "$worker"
  fi
done
sudo -n systemctl stop "$API_SERVICE"
api_stopped=true
sudo -n systemd-run --wait --pipe --collect \
  --unit="mikanquiz-db-backup-$(date +%s)-$$" \
  --property=User=ubuntu --property=Group=root \
  --property=WorkingDirectory="$PROD_BACKEND_DIR" \
  --property=EnvironmentFile="$ENV_FILE" \
  "$PROD_VENV/bin/python" "$SRC_WEB_DIR/scripts/backup_sqlite.py" \
  --database "$DATABASE_FILE" --destination "$BACKUP_DIR"

phase=sync-code
echo '=== 3. 同步代码，保留生产环境文件 ==='
rsync -a --delete \
  --exclude='.venv' --exclude='var' \
  --exclude='.env' --exclude='.env.*' \
  --exclude='__pycache__' --exclude='*.pyc' \
  "$SRC_WEB_DIR/backend/" "$PROD_BACKEND_DIR/"
mkdir -p "$PROD_UPLOADER_DIR" "$PROD_WEB_DIR/scripts"
rsync -a --delete --exclude='node_modules' --exclude='.env' --exclude='.env.*' \
  "$SRC_WEB_DIR/r2-uploader/" "$PROD_UPLOADER_DIR/"
rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' \
  "$SRC_WEB_DIR/scripts/" "$PROD_WEB_DIR/scripts/"

phase=dependencies-and-migration
echo '=== 4. 按需安装依赖，使用生产配置执行迁移 ==='
# No automatic pip upgrade and no frontend build on the server.
if [[ "$install_backend_deps" == true ]]; then
  "$PROD_VENV/bin/python" -m pip install -r "$PROD_BACKEND_DIR/requirements.txt" --quiet
fi
if [[ "$install_uploader_deps" == true ]]; then
  npm --prefix "$PROD_UPLOADER_DIR" ci --omit=dev --silent
fi
sudo -n systemd-run --wait --pipe --collect \
  --unit="mikanquiz-db-migrate-$(date +%s)-$$" \
  --property=User=ubuntu --property=Group=root \
  --property=WorkingDirectory="$PROD_BACKEND_DIR" \
  --property=EnvironmentFile="$ENV_FILE" \
  "$PROD_VENV/bin/alembic" upgrade head

phase=publish-and-check
echo '=== 5. 部署前端、启动并检查 API ==='
mkdir -p "$PROD_FRONTEND_DIR"
rsync -a --delete "$SRC_WEB_DIR/frontend/dist/" "$PROD_FRONTEND_DIR/"
sudo -n nginx -t
sudo -n systemctl start "$API_SERVICE"
sudo -n systemctl is-active --quiet "$API_SERVICE"
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 1 \
  --connect-timeout 2 --max-time 5 http://127.0.0.1:8000/api/health \
  | "$PROD_VENV/bin/python" -c 'import json,sys; data=json.load(sys.stdin); assert data.get("status")=="ok" and data.get("database")=="ok", data; print("API 与数据库健康检查通过")'
sudo -n systemctl reload nginx
# Only resume timers that were active before deployment.
if [[ -f "$timer_state_file" ]]; then
  while IFS= read -r timer; do
    sudo -n systemctl start "$timer"
  done < "$timer_state_file"
fi
rm -f "$timer_state_file"
api_stopped=false
echo '=== 部署完成。请再检查线上首页、登录、图片及字体预览 ==='
