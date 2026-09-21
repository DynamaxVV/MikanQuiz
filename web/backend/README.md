# 独立后端

这是小程序与 Web 共用的 FastAPI 单体服务。生产运行在单个 Uvicorn worker、SQLite 本地磁盘和宿主机 Nginx 后面；数据库结构只由 Alembic 迁移创建，应用启动**不会**调用 `create_all()`。

## 本地运行

```sh
cd web/backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
export QUIZ_DATABASE_URL="sqlite:///$(pwd)/var/quiz.db"
mkdir -p var
alembic upgrade head
python -m app.admin_cli add operator
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

测试会为每次运行建立临时 SQLite 文件，并从空库执行 Alembic：

```sh
python -m pytest tests -q
# 从仓库根目录执行时（仍需先激活上述 .venv）：
python -m pytest web/backend/tests -q
```

生产环境变量仅有：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `QUIZ_DATABASE_URL` | `sqlite:///./quiz.db` | 本机 SQLite 路径；不可指向 OSS/NFS |
| `QUIZ_ADMIN_SESSION_HOURS` | `8` | 管理员 Bearer token 有效期 |
| `QUIZ_COOKIE_SECURE` | `true` | Web 管理 Cookie 是否只允许 HTTPS；本地测试设为 `false` |
| `QUIZ_CONFIG_MAX_BYTES` | `10485760` | 完整配置 JSON 导入的应用层请求体上限；Nginx 样例同步为 `10m` |
| `QUIZ_FONT_SOURCE_ORIGINS` | 空 | 允许导入字体 URL 的额外 HTTPS origin，逗号分隔；不会读取或探测远程内容 |
| `QUIZ_LOG_LEVEL` | `INFO` | 应用 JSON 日志级别；可选 `DEBUG`、`INFO`、`WARNING`、`ERROR` |
| `QUIZ_ACCESS_LOG_PATH` | 空 | 关键访问/审计事件 JSONL 文件；生产建议 `/srv/quiz/data/quiz-access.jsonl` |
| `QUIZ_ACCESS_LOG_MAX_BYTES` | `20971520` | 当前文件达到 20 MiB 后轮转 |
| `QUIZ_ACCESS_LOG_BACKUP_COUNT` | `14` | 额外保留 14 个轮转文件 |
| `QUIZ_FEEDBACK_SMTP_HOST` | 空 | 反馈通知 SMTP 主机；留空则只保存反馈 |
| `QUIZ_FEEDBACK_SMTP_PORT` | `587` | 反馈通知 SMTP 端口 |
| `QUIZ_FEEDBACK_SMTP_USERNAME` | 空 | SMTP 登录账号 |
| `QUIZ_FEEDBACK_SMTP_PASSWORD` | 空 | SMTP 登录密码；不要提交到仓库 |
| `QUIZ_FEEDBACK_SMTP_STARTTLS` | `true` | 是否在 SMTP 连接上启用 STARTTLS |
| `QUIZ_FEEDBACK_EMAIL_FROM` | 空 | 反馈通知发件地址；为空时使用 SMTP 账号 |
| `QUIZ_FEEDBACK_EMAIL_TO` | 空 | 反馈通知收件地址，多个地址用逗号分隔 |
| `QUIZ_FEEDBACK_RATE_LIMIT_PER_HOUR` | `5` | 同一客户端每小时最多提交的反馈数 |

## API 合约

所有 API 使用 JSON、snake_case 字段和 `/api/v1` 前缀。预期业务错误一律为：

```json
{"error":{"code":"ATTEMPT_EXPIRED","message":"本次答题已过期，请重新开始"}}
```

字段名与响应外壳固定如下。`datetime` 为 ISO 8601 UTC 时间；匿名公开题目永远没有 `answer` 和 `explanation`。

### 公开答题

`GET /api/v1/quiz/settings` 返回：

```json
{
  "question_count": 10,
  "modes": {
    "beginner": [90, 10, 0],
    "proficient": [40, 40, 20],
    "challenge": [10, 40, 50]
  },
  "font_presets": []
}
```

`POST /api/v1/quiz/attempts` 请求 `{"mode":"beginner"}`，返回 `201`：

```json
{
  "attempt_token": "仅在这次响应中返回的高熵令牌",
  "mode": "beginner",
  "expires_at": "2026-07-23T00:00:00+00:00",
  "questions": [
    {"id": 1, "text": "题干", "image_url": "https://...", "difficulty": 1,
     "options": ["选项 A", "选项 B", "选项 C", "选项 D"]}
  ]
}
```

客户端把 `attempt_token` 仅保存到同一设备的本地存储，后续恢复与提交都带 `X-Quiz-Attempt: <token>`：

```text
GET  /api/v1/quiz/attempts/current
POST /api/v1/quiz/attempts/submit
```

昵称是可选字段；客户端可直接离开答题页，或清除本地 attempt token 和答案后重新选择难度开始新练习。

提交请求：

```json
{"display_name":"小明","answers":{"1":"A","8":"D"}}
```

必须刚好包含 attempt 绑定的所有题目；额外、缺失或非法值均拒绝。成功和同一 token 的重试都返回同一份结果：

```json
{
  "submission_id": 42,
  "display_name": "小明",
  "mode": "beginner",
  "score": 50,
  "correct_count": 1,
  "total": 2,
  "submitted_at": "2026-07-22T00:00:00+00:00",
  "details": [{
    "question_id": 1,
    "question_text": "题干",
    "image_url": "https://pan.yurucamp.cn/example.png",
    "options": ["选项 A", "选项 B", "选项 C", "选项 D"],
    "selected": "A",
    "correct_answer": "B",
    "explanation": "统一解析",
    "is_correct": false
  }]
}
```

### 管理员认证

管理员由服务器 CLI 创建、改密、停用或恢复，Web 没有账号管理页面：

```sh
python -m app.admin_cli add USERNAME
python -m app.admin_cli list
python -m app.admin_cli password USERNAME
python -m app.admin_cli disable USERNAME
python -m app.admin_cli enable USERNAME
```

`POST /api/v1/admin/web/login` 和 `POST /api/v1/admin/miniprogram/login` 都请求：

```json
{"username":"operator","password":"至少 8 个字符"}
```

Web 登录只返回：

```json
{"expires_at":"2026-07-22T08:00:00+00:00","username":"operator"}
```

同时设置 `HttpOnly; Secure; SameSite=Lax` 的 `quiz_admin_session` Cookie。Web `fetch` 必须使用同源请求和 `credentials: "include"`；前端不接触令牌原文。

小程序登录返回可保存的 Bearer token：

```json
{"token":"Bearer 令牌原文","expires_at":"2026-07-22T08:00:00+00:00","username":"operator"}
```

小程序以 `Authorization: Bearer <token>` 请求管理 API；Web 自动发送上述 Cookie。`POST /api/v1/admin/logout` 返回 `204` 并清除 Cookie；`GET /api/v1/admin/session` 返回当前 `username` 和 `expires_at`。

### 题库、设置与提交记录

所有下列接口都要求管理员 Bearer token：

| Method | Path | Request/response |
| --- | --- | --- |
| `GET` | `/admin/questions?page=1&page_size=20&query=&difficulty=` | `{items, page, page_size, total}`，每项是完整题目 |
| `POST` | `/admin/questions` | 完整题目；返回 `201` 和完整题目 |
| `GET` | `/admin/questions/{id}` | 完整题目 |
| `POST` | `/admin/images` | multipart 表单字段 `image`；返回 `{image_url}` |
| `PATCH` | `/admin/questions/{id}` | 完整题目字段的任意子集；返回完整题目 |
| `DELETE` | `/admin/questions/{id}` | `204` |
| `POST` | `/admin/font-references` | 新增 `{title,image_url,note,difficulty}` 嵌字笔记卡片 |
| `PATCH` | `/admin/font-references/{id}` | 部分更新 `{title,image_url,note,difficulty}` 任意字段 |
| `DELETE` | `/admin/font-references/{id}` | `204`，删除卡片 |
| `GET` | `/admin/settings` | 完整 settings 对象 |
| `PUT` | `/admin/settings/strategy` | `{"question_count":10,"modes":{...}}` |
| `PUT` | `/admin/settings/font-presets` | `{"font_presets":["甲","乙"]}` |
| `GET` | `/admin/submissions?page=1&page_size=20&display_name=&from=&to=` | `{items, page, page_size, total}` |
| `GET` | `/admin/submissions/{id}` | 上述完整提交结果和历史快照 |

完整题目 JSON：

```json
{
  "id": 1,
  "text": "请选择正确字形",
  "image_url": "https://pan.yurucamp.cn/example.png",
  "difficulty": 3,
  "options": ["甲", "乙", "丙", "丁"],
  "answer": "B",
  "explanation": "统一解析",
  "created_at": "2026-07-22T00:00:00+00:00",
  "updated_at": "2026-07-22T00:00:00+00:00"
}
```

创建时不包含 `id`、时间字段；`image_url` 可为 `null`，非空时必须是 HTTPS。答案固定 `A`–`D`，选项固定四个，题干最长 500 字，解析最长 1000 字。

`GET /api/health` 是 Nginx/systemd 的健康检查，只返回 `{"status":"ok","database":"ok"}`。

公开嵌字笔记卡片使用 `GET /api/v1/font-references`，无需管理员认证。

### 完整配置迁移

管理端 `/admin/config` 提供一个 `mikanquiz-admin-config.json` 文件的导出、只读预览和确认导入：

| Method | Path | 作用 |
| --- | --- | --- |
| `GET` | `/admin/config/export` | 导出题库、字体分区/字体、出题设置和嵌字笔记 |
| `POST` | `/admin/config/import/validate` | 校验 manifest、检查字体来源并返回当前/导入 SHA-256 与差异 |
| `POST` | `/admin/config/import` | 使用预览哈希和 `confirm: true` 原子替换配置实体 |

文件格式固定为 `{"format":"mikanquiz-admin-config","version":1,...}`。题目、分区、字体和笔记使用迁移稳定的 `config_key`，不保存本机整数 ID；`exported_at` 只属于传输元数据，不参与哈希。导入只支持 `mode: "replace"`，要求管理员先预览，提交 `expected_current_hash`、`expected_incoming_hash` 和显式确认。管理员账号、会话、答题 attempt、提交历史不会被替换；原始图片和字体对象也不会被删除，只会更新数据库配置和派生 JSON 同步任务。

导入会在 SQLite `BEGIN IMMEDIATE` 下重新计算当前哈希并再次检查未提交且未过期的答题会话；如果将删除的题目仍被引用，返回 `ACTIVE_ATTEMPT_CONFLICT`，不会产生部分写入。字体 URL 必须是 HTTPS，且只能来自当前 `QUIZ_R2_PUBLIC_BASE_URL` 或 `QUIZ_FONT_SOURCE_ORIGINS`；系统保留分区不能从 manifest 中省略。错误响应中的 `details` 最多返回 200 项，并以 `errors_truncated` 标记截断。

### 单独题库迁移

管理端 `/admin/config` 页面同时提供独立的题库 JSON 工具，适合日常批量维护，不会改动字体目录、出题策略或嵌字笔记：

| Method | Path | 作用 |
| --- | --- | --- |
| `GET` | `/admin/questions/export` | 下载当前全部题目为 `questions-YYYY-MM-DD_HH-mm-ss.json` |
| `POST` | `/admin/questions/import` | 校验并追加 JSON 中的题目，返回读取/新增/失败统计 |

导出文件格式为 `{"version":1,"exported_at":"...","questions":[...]}`。每项包含 `id`、`text`、`image_url`、`difficulty`、`correct_option_id`、`explanation`、`created_at` 和 `updated_at`；导入时忽略 `id` 与时间字段，允许额外字段，现有题目不会被覆盖或去重，重复导入同一文件会再次追加。`correct_option_id` 非空时必须指向当前字体目录中的有效字体；单条校验失败不会阻止其他有效题目导入，响应中的 `errors` 会说明失败原因。`image_url` 可以为 `null`，图片地址按文件内容保存。

### 管理端图片上传

`POST /api/v1/admin/images` 仅接受已登录管理员的 multipart 文件字段 `image`，支持 8MB 以内的 JPG、PNG、GIF、WebP。FastAPI 默认从服务器环境变量读取 Cloudflare R2 凭据，经 AWS SDK v3 上传并返回公开 URL；浏览器与小程序不会收到凭据。本地调试可在 `.env` 设置 `QUIZ_STORAGE_BACKEND=local`，图片会写入 `QUIZ_LOCAL_STORAGE_PATH`（默认 `./var/uploads`），并从 `QUIZ_LOCAL_PUBLIC_BASE_URL`（默认 `http://127.0.0.1:8000/uploads`）读取；此模式仅用于本地开发，不应部署到公网。

复制 `.env.example` 为 `.env` 后填写上述四个值。启动时默认读取该文件；环境变量优先，可使用 `QUIZ_ENV_FILE` 指向服务器上权限为 `0600` 的配置文件。

本地模式的上传目录为 `QUIZ_LOCAL_STORAGE_PATH`，路径会被后端挂载到 `QUIZ_LOCAL_PUBLIC_BASE_URL` 的 URL 路径。生产环境继续使用 R2，不要把本地模式的上传目录暴露到公网。

### 用户反馈

`POST /api/v1/feedback` 接受匿名反馈，正文最多 2000 字，可选填写联系 QQ 号，并支持最多 3 张 JPG、PNG 或 WebP 图片，每张不超过 3MB。图片使用独立的 `feedback/` 前缀保存；邮件通知正文包含反馈内容、联系 QQ 号、答题摘要和图片 URL，不直接发送图片附件。SMTP 未配置或投递失败时，反馈记录仍会保存在数据库中。

## 运维边界

- SQLite 使用 WAL、foreign keys、5 秒 busy timeout 和 `synchronous=NORMAL`，只运行一个 Uvicorn worker。
- 令牌和密码原文不会写入数据库；密码使用 Argon2，令牌只保存 SHA-256 摘要。
- 停用管理员会撤销其全部会话；CLI 拒绝停用最后一个有效管理员。
- 业务表不写 IP。限流、真实 IP 转发、请求大小和 TLS 由 Nginx 管理。
- 应用日志为 stdout 的单行 JSON，由 systemd journald 收集；日志含真实用户 IP、请求 ID、管理员审计和 R2 上传事件。关键 HTTP/答题/管理员认证事件会额外写入 `QUIZ_ACCESS_LOG_PATH` 指定的轮转 JSONL 文件。部署时安装 `../deploy/mikan-quiz-journald.conf.example`，并使用 `journalctl -u <实际服务名> -o cat | jq` 或 `jq` 查询该文件。完整字段和隐私边界见 [`LOGGING_DESIGN_ZH.md`](LOGGING_DESIGN_ZH.md)。
- `../scripts/backup_sqlite.py` 用 SQLite 在线备份 API 生成快照；`../scripts/migrate_cloud_export.py` 只在完成图片 URL 映射后导入旧云导出数据。
- `../scripts/cleanup_expired_attempts.py` 由 `quiz-cleanup.timer` 每小时清理过期且未提交的 attempt；已提交记录永不由该任务删除。
- 管理配置变更只写入 `sync_outbox`，不在 API 请求中执行 R2 网络操作。安装 `../deploy/quiz-sync.service` 和 `quiz-sync.timer`，由 `../scripts/sync_worker.py --drain` 重建 `sync/questions/{id}.json`、`sync/questions/all.json`、`sync/notes/{section_id}.json` 和 `sync/notes/all.json`；任务按 scope 单飞、带租约/围栏、失败指数退避，终态失败可用 `--outbox-id ID` 人工重试。

迁移历史提交时，`answers` 中必须含完整历史快照：`questionId`、`selected`、`isCorrect`、`correctAnswer`、`questionText`、`imageUrl`（可为空）、`options`（四项）和 `explanation`；提交本身还必须含 `score`、`correctCount`、`total`、`submittedAt`。脚本只使用这些导出值写入历史，并验证它们彼此一致。旧导出若只含 `selected/isCorrect` 会安全失败，绝不使用当前题库的答案、解析、选项或图片反推历史。

部署 Nginx 时，`../deploy/nginx.http.conf.example` 必须安装到由主配置 `http {}` 引入的位置（Ubuntu 默认可用 `/etc/nginx/conf.d/`）；`../deploy/nginx.conf.example` 才是 `sites-enabled` 的 `server {}` 文件。还要将 `nginx.proxy-headers.conf.example` 安装为 `/etc/nginx/snippets/quiz-proxy-headers.conf`。填写真实备案中转 IP/CIDR 的 `set_real_ip_from` 后，样例会覆盖任何客户端伪造的 `X-Forwarded-For`，只将可信 `$remote_addr` 转发给应用。部署前运行 `nginx -t`；本机没有 Nginx 时可先执行 `python web/deploy/verify_nginx_example.py` 做静态检查。

迁移历史提交时，`answers` 中必须含完整历史快照：`questionId`、`selected`、`isCorrect`、`correctAnswer`、`questionText`、`imageUrl`（可为空）、`options`（四项）和 `explanation`；提交本身还必须含 `score`、`correctCount`、`total`、`submittedAt`。脚本只使用这些导出值写入历史，并验证它们彼此一致。旧导出若只含 `selected/isCorrect` 会安全失败，绝不使用当前题库的答案、解析、选项或图片反推历史。
