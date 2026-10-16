# Web 部署与维护

本文是当前 Web 产品的部署入口，适用于单机 Ubuntu、Nginx、systemd、FastAPI 单 worker 和本地磁盘 SQLite。旧小程序、云函数不参与部署。本地开发见 [Web 说明](../README.md)，界面设计约定见 [DESIGN.md](../../DESIGN.md)。

以下命令供部署者在目标服务器执行；仓库检查通过不代表已完成真实服务器部署验收。示例域名 `quiz.example.com`、图片域名 `images.example.com`、R2 凭据和备份文件名都必须替换。

## 1. 目录与前提

需要 Python 3.10+、Node.js 22.18+、npm、Git、Nginx 和 systemd。前端使用仓库中的 `dist/` 时无需在服务器构建；R2 适配器仍需要 Node.js。部署前检查 `python3 --version`、`node --version`，不要假定系统软件源一定提供所需 Node.js 版本。

本文固定使用下列布局，与同目录的服务模板一致：

| 路径 | 内容 |
| --- | --- |
| `/srv/quiz/repo/` | Git 仓库，由部署操作员维护 |
| `/srv/quiz/current` | 指向 `/srv/quiz/repo/web` 的软链接，**不是仓库根目录** |
| `/srv/quiz/venv/` | Python 生产虚拟环境 |
| `/srv/quiz/data/quiz.db` | 持久数据库，不放在代码目录中 |
| `/srv/quiz/data/backups/` | 数据库备份 |
| `/etc/quiz/quiz-api.env` | 生产配置，不提交 Git |

已有部署若使用其他路径或服务名，先核对 `systemctl cat <服务名>` 与 `nginx -T`，按实际值替换本文命令，不要另建空数据库或覆盖现有配置。数据库 URL 必须是实际生产库的绝对路径。

## 2. 首次部署：代码、用户和依赖

以下示例由有 sudo 权限的普通部署操作员执行；若 `quiz` 用户已存在，跳过创建：

```sh
sudo apt update
sudo apt install git nginx python3-venv python3-pip sqlite3 curl
sudo useradd --system --home /srv/quiz --shell /usr/sbin/nologin quiz
sudo install -d -m 755 /srv/quiz
sudo install -d -o "$USER" -g "$(id -gn)" -m 755 /srv/quiz/repo /srv/quiz/venv
sudo install -d -o quiz -g quiz -m 750 /srv/quiz/data /srv/quiz/data/backups
sudo install -d -o root -g quiz -m 750 /etc/quiz

git clone https://github.com/DynamaxVV/MikanQuiz.git /srv/quiz/repo
sudo ln -s /srv/quiz/repo/web /srv/quiz/current
python3 -m venv /srv/quiz/venv
/srv/quiz/venv/bin/python -m pip install -r /srv/quiz/current/backend/requirements.txt
npm --prefix /srv/quiz/current/r2-uploader ci --omit=dev
```

代码和虚拟环境必须允许 `quiz` 用户读取、目录可遍历，前端静态文件还需允许 Nginx 用户读取。不要将代码目录或虚拟环境设为全员可写。服务模板限制持久写入 `/srv/quiz/data`，临时文件写入服务私有 `/tmp`。

当前 Python 依赖只有部分固定版本。应记录实际部署版本；下列文件用于排查和复现，不是自动生成的跨环境锁文件：

```sh
/srv/quiz/venv/bin/python -m pip freeze | sudo -u quiz tee /srv/quiz/data/deployed-requirements.txt > /dev/null
```

## 3. 生产配置与数据库初始化

仅首次创建配置文件，已有文件直接编辑：

```sh
sudo install -o quiz -g quiz -m 600 /dev/null /etc/quiz/quiz-api.env
sudoedit /etc/quiz/quiz-api.env
```

填写下列内容，R2 密钥只保存在此文件中。生产配置必须显式使用 `r2`；开发用 `.env.example` 默认是 `local`，不可原样用于上线。

```dotenv
QUIZ_DATABASE_URL=sqlite:////srv/quiz/data/quiz.db
QUIZ_COOKIE_SECURE=true
QUIZ_ADMIN_SESSION_HOURS=8
QUIZ_STORAGE_BACKEND=r2
QUIZ_R2_ENDPOINT=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
QUIZ_R2_ACCESS_KEY_ID=REPLACE_ME
QUIZ_R2_SECRET_ACCESS_KEY=REPLACE_ME
QUIZ_R2_BUCKET=REPLACE_ME
QUIZ_R2_PUBLIC_BASE_URL=https://images.example.com
QUIZ_ACCESS_LOG_PATH=/srv/quiz/data/quiz-access.jsonl
QUIZ_CONFIG_MAX_BYTES=10485760
```

R2 需准备 bucket、可读取图片和字体的公共 HTTPS 域名，以及允许该 bucket 所需读写/删除操作的凭据。配置备份包含对象 URL，不包含原始 R2 文件；应另行保护 bucket 中的媒体对象。可选字体来源白名单与反馈 SMTP 配置见 [后端环境变量表](../backend/README.md)。

从持有 `alembic.ini` 的后端目录执行初始化。CLI 显式读取同一生产配置，不在终端打印或 `source` 整份密钥文件：

```sh
cd /srv/quiz/current/backend
sudo -u quiz env QUIZ_ENV_FILE=/etc/quiz/quiz-api.env /srv/quiz/venv/bin/alembic upgrade head
sudo -u quiz env QUIZ_ENV_FILE=/etc/quiz/quiz-api.env /srv/quiz/venv/bin/alembic current
sudo -u quiz env QUIZ_ENV_FILE=/etc/quiz/quiz-api.env /srv/quiz/venv/bin/python -m app.admin_cli add operator
```

管理员密码交互式设置。首次数据库为空，登录管理端后配置字体、题目和嵌字笔记，或使用配置页导入自己的数据。

## 4. 安装 API、同步和清理服务

```sh
sudo install -m 644 /srv/quiz/current/deploy/quiz-api.service /etc/systemd/system/
sudo install -m 644 /srv/quiz/current/deploy/quiz-sync.service /srv/quiz/current/deploy/quiz-sync.timer /etc/systemd/system/
sudo install -m 644 /srv/quiz/current/deploy/quiz-cleanup.service /srv/quiz/current/deploy/quiz-cleanup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quiz-api.service
curl --fail http://127.0.0.1:8000/api/health
sudo systemctl enable --now quiz-sync.timer quiz-cleanup.timer
sudo systemctl list-timers 'quiz-*'
```

健康响应应为 `{"status":"ok","database":"ok"}`。API 仅监听 `127.0.0.1:8000`、单 worker。同步任务每分钟处理 R2 JSON outbox；清理任务每小时删除过期且未提交的答题会话，不删除已提交历史。它们通过 `EnvironmentFile` 读取同一数据库路径。

## 5. Nginx 与 HTTPS

先让站点域名解析到服务器，准备该域名有效的证书与私钥。尚无证书时，可用 HTTP 验证申请证书：安装 `certbot`，将下面的 HTTP 站点保存为 `/etc/nginx/sites-available/quiz-http.conf`，替换域名后启用。这里的 80 端口需能从公网访问。

```nginx
server {
    listen 80;
    server_name quiz.example.com;
    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }
    location / { return 301 https://$host$request_uri; }
}
```

```sh
sudo apt install certbot
sudo install -d -m 755 /var/www/letsencrypt
sudo ln -s /etc/nginx/sites-available/quiz-http.conf /etc/nginx/sites-enabled/quiz-http.conf
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/letsencrypt -d quiz.example.com
```

证书可用后安装 HTTPS 站点及两个配套片段：

```sh
sudo install -m 644 /srv/quiz/current/deploy/nginx.http.conf.example /etc/nginx/conf.d/quiz-rate-limits.conf
sudo install -d /etc/nginx/snippets
sudo install -m 644 /srv/quiz/current/deploy/nginx.proxy-headers.conf.example /etc/nginx/snippets/quiz-proxy-headers.conf
sudo install -m 644 /srv/quiz/current/deploy/nginx.conf.example /etc/nginx/sites-available/quiz.conf
sudoedit /etc/nginx/sites-available/quiz.conf
```

编辑时逐项完成：

- 替换 `server_name`，取消证书配置注释并填写证书与私钥实际路径。
- 确认 `root /srv/quiz/current/frontend/dist` 对应当前构建产物。
- 将 CSP 中的 `images.example.com` 替换为 R2 公共图片域名；保留 `blob:`、`data:` 供管理端本地图片预览使用，字体通过同源 API 加载。
- 只有存在可信前置代理时才配置 `set_real_ip_from`、`real_ip_header` 等，填写真实代理来源，不能信任任意客户端地址。直连部署保留注释。
- 全局上传上限示例为 `64m`，覆盖 40 MiB 字体及 multipart 开销；配置导入单独限制为 `10m`。PDF 应用层上限 20 MiB，普通图片为 8 MiB。

```sh
sudo ln -s /etc/nginx/sites-available/quiz.conf /etc/nginx/sites-enabled/quiz.conf
sudo nginx -t
sudo systemctl reload nginx
curl --fail https://quiz.example.com/api/health
```

不要把含 `limit_req_zone` 的 `nginx.http.conf.example` 安装到 `sites-enabled` 的 `server {}` 内。证书续期后需 reload Nginx 才会载入新证书；若使用 Certbot，可在 `/etc/letsencrypt/renewal-hooks/deploy/` 配置可执行的 `nginx -t && systemctl reload nginx` 脚本，并检查系统的续期定时器。

## 6. 前端站点配置与上线检查

仓库 `web/frontend/dist/` 是预构建的当前站点版本，可以直接部署。要改变招募信息等站点内容，在构建机器的 `web/frontend/.env.local` 填写配置后重建：

```sh
cd /srv/quiz/repo/web/frontend
npm ci
# 仅首次复制；已有文件直接编辑
cp .env.example .env.local
# 编辑 .env.local 后再构建
npm run build
```

上述命令会覆盖当前 `dist/`，应在维护窗口执行，或先在独立构建目录生成后发布。`VITE_*` 配置会进入公开 JS；后端密钥不得写入前端配置。若部署流程将 `dist/` 复制到独立静态目录，以 `nginx -T` 的实际 `root` 为准，例如执行 `rsync -a --delete <构建目录>/ <已确认的静态目录>/`；不要假定其他服务器使用同一路径。

上线至少验证：首页和插画、管理员登录、题图选择后的本地预览与保存、字体预览、笔记 PDF 上传下载、完整答题与提交结果。检查浏览器控制台没有 CSP/资源加载错误，同时确认 API 健康和同步任务状态。健康接口成功不代表这些业务操作已验收。

## 7. 日常更新

以下流程用于本文的 Git checkout 布局。先记录旧提交，检查工作区，确认服务器没有需要保留的本地源码或构建改动；有改动时先处理，不使用 reset 或 clean 强行更新。

```sh
cd /srv/quiz/repo
git status --short
git rev-parse HEAD
sudo -u quiz /srv/quiz/venv/bin/python /srv/quiz/current/scripts/backup_sqlite.py --database /srv/quiz/data/quiz.db --destination /srv/quiz/data/backups
```

**仅更新前端静态文件**：确认远端提交已包含正确站点配置生成的 `dist/`，执行 `git pull --ff-only`。本文 Nginx 直接读取此目录，无需重启 API；使用独立静态目录的部署还需复制产物。更新期间浏览器可能请求旧 hash 文件，可在低峰发布，并保留上一版静态资源直至旧页面退出。

**包含后端、迁移或依赖变更**：在维护窗口停止写入与定时任务，再更新；使用事先记录的旧提交准备回退。

如已配置备份定时器，先停止 `quiz-backup.timer` 和 `quiz-backup.service`；未安装时跳过这两个 unit。下列停止 API 后生成的快照是本次维护前的最终备份：

```sh
sudo systemctl stop quiz-sync.timer quiz-cleanup.timer
sudo systemctl stop quiz-sync.service quiz-cleanup.service quiz-api.service
sudo -u quiz /srv/quiz/venv/bin/python /srv/quiz/current/scripts/backup_sqlite.py --database /srv/quiz/data/quiz.db --destination /srv/quiz/data/backups
git pull --ff-only
/srv/quiz/venv/bin/python -m pip install -r /srv/quiz/current/backend/requirements.txt
npm --prefix /srv/quiz/current/r2-uploader ci --omit=dev
cd /srv/quiz/current/backend
sudo -u quiz env QUIZ_ENV_FILE=/etc/quiz/quiz-api.env /srv/quiz/venv/bin/alembic upgrade head
sudo -u quiz env QUIZ_ENV_FILE=/etc/quiz/quiz-api.env /srv/quiz/venv/bin/alembic current
sudo systemctl start quiz-api.service
curl --fail http://127.0.0.1:8000/api/health
sudo systemctl start quiz-sync.timer quiz-cleanup.timer
```

备份定时器仅在已配置时恢复启动。服务模板有修改时，重新安装对应 unit 并 `systemctl daemon-reload` 后再启动。Nginx 配置有修改时，先 `nginx -t` 再 reload。任一步失败就停止后续更新，保留日志与备份；迁移失败时不要先启动 API。

## 8. 备份、恢复与版本回退

第 7 节的备份命令通过 SQLite 在线备份 API 生成一致性快照、检查完整性、压缩并生成 `.sha256`。不能在服务写入 WAL 时只复制 `quiz.db`。

需要每日自动上传 OSS 时，另行安装并配置 `ossutil`，让 `quiz` 用户可读取其配置；在 `/etc/quiz/quiz-backup.env`（`quiz:quiz`、`0600`）设置 `QUIZ_OSS_TARGET=oss://YOUR_BUCKET/quiz-backups/`。然后安装、手动试运行并检查成功，再启用定时器：

```sh
sudo install -m 644 /srv/quiz/current/deploy/quiz-backup.service /srv/quiz/current/deploy/quiz-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start quiz-backup.service
sudo journalctl -u quiz-backup.service -n 50 --no-pager
sudo systemctl enable --now quiz-backup.timer
```

未配置 OSS 时不启用这个模板，仍可手动执行本地备份。脚本保留最近 7 日和 4 周的本地快照；远端 OSS 的保留期需另行配置。数据库备份不包括 R2 对象、环境配置、代码和浏览器 IndexedDB 草稿。

**恢复步骤**：先在临时位置验证备份，再进入维护窗口。以下文件名是占位示例，先替换为实际备份文件名：

```sh
cd /srv/quiz/data/backups
sudo -u quiz sha256sum -c quiz-TIMESTAMP-REVISION.sqlite.gz.sha256
sudo -u quiz gzip -dk quiz-TIMESTAMP-REVISION.sqlite.gz
sudo -u quiz sqlite3 quiz-TIMESTAMP-REVISION.sqlite 'PRAGMA integrity_check; SELECT version_num FROM alembic_version;'
```

校验应返回 `ok` 和已知迁移版本。停止第 7 节列出的定时器、任务与 API 后，保留旧数据库整组文件，再复制已验证的快照：

```sh
# 替换为上一步解压、校验过的实际文件
QUIZ_RESTORE_FILE=/srv/quiz/data/backups/quiz-TIMESTAMP-REVISION.sqlite
QUIZ_RECOVERY_DIR=/srv/quiz/data/before-restore-$(date +%Y%m%d-%H%M%S)
sudo install -d -o quiz -g quiz -m 750 "$QUIZ_RECOVERY_DIR"
for suffix in '' -wal -shm; do
    if sudo test -e "/srv/quiz/data/quiz.db$suffix"; then
        sudo mv "/srv/quiz/data/quiz.db$suffix" "$QUIZ_RECOVERY_DIR/"
    fi
done
sudo install -o quiz -g quiz -m 600 "$QUIZ_RESTORE_FILE" /srv/quiz/data/quiz.db
```

不要让旧 WAL/SHM 与恢复后的数据库混用。使用匹配备份版本的代码和依赖启动；若恢复到当前代码，先对副本验证迁移再执行生产 `alembic upgrade head`。重新检查健康、题库、管理员、提交历史及 R2 文件，最后恢复定时器。

**代码回退**：记录旧提交和匹配的依赖，在无本地改动的代码目录切换到已确认版本，再恢复相应前端产物、依赖和服务配置。数据库已迁移时，不能仅回退代码；需确认 schema 兼容，或在明确接受备份之后数据丢失的前提下恢复备份。不默认执行 `alembic downgrade`。使用共享虚拟环境时，切换代码也不会自动回退依赖。

## 9. 字体缓存预热

这是可选性能优化，必须先有字体目录和可访问的字体 URL。当前缓存位于服务私有 `/tmp/mikanquiz-font-subsets`、`/tmp/mikanquiz-raw-fonts`，重启后可能失效。普通 shell 直接执行预热脚本会使用另一套 `/tmp`。

API 已启动时，可用临时 systemd 服务加入其命名空间，并读取同一生产配置：

```sh
sudo systemd-run --wait --pipe --collect --unit=quiz-font-prewarm \
  --property=User=quiz --property=Group=quiz \
  --property=PrivateTmp=yes --property=JoinsNamespaceOf=quiz-api.service \
  --property=Requires=quiz-api.service --property=After=quiz-api.service \
  --property=WorkingDirectory=/srv/quiz/current/backend \
  --property=EnvironmentFile=/etc/quiz/quiz-api.env \
  /srv/quiz/venv/bin/python /srv/quiz/current/backend/scripts/prewarm_fonts.py
```

检查脚本输出中的成功、回退和失败数量；脚本即使部分字体失败也可能退出 0。`X-Font-Subset: hit` 本身不能证明预热生效，应结合实际缓存和浏览器字体显示验证。

## 10. 常见问题

| 现象 | 先检查 |
| --- | --- |
| API 无法启动、502 | `systemctl status quiz-api.service`、`journalctl -u quiz-api.service -n 100`，确认路径和读取/写入权限 |
| 表不存在、题库意外为空 | 实际 unit 的环境文件与 `QUIZ_DATABASE_URL`，在同一配置下运行 `alembic current`；不要先建空库 |
| 本地可登录、线上登录不保持 | HTTPS、`QUIZ_COOKIE_SECURE`、同源 API 路径和代理协议头 |
| 图片选择后预览空白 | 浏览器 CSP 报错，`img-src` 是否含 `blob:`，R2 图片域名是否正确 |
| 上传 413 | Nginx 与前置代理的上传限制；配置导入、字体、图片、PDF 分别有不同应用上限 |
| R2 上传失败 | Node.js 是否在 systemd 的 PATH 中、适配器依赖是否安装、凭据权限和公网域名是否正确 |
| 字体预览失败 | `/api/v1/fonts/stream` 的响应与 API 日志、字体来源许可、字体文件可用性与私有缓存 |
| JSON 同步未更新 | `systemctl status quiz-sync.timer`、`journalctl -u quiz-sync.service`；查看 outbox 后再按 ID 重试 |
| 备份失败 | 数据目录权限、OSS 配置与 `journalctl -u quiz-backup.service`；定时器启用不等于上传成功 |

详细日志字段与脱敏边界见 [日志说明](../backend/LOGGING_DESIGN_ZH.md)。分享诊断资料前移除 Cookie、Authorization、密钥、用户反馈联系方式等敏感内容。
