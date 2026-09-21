# 小程序与 Web 共用后端：技术选型与迁移方案

## 1. 文档状态

- 状态：已确认方案
- 日期：2026-07-21
- UI 设计合同：[`../DESIGN.md`](../DESIGN.md)
- 当前系统：微信小程序 + 微信云函数 + 微信云数据库/云存储
- 目标系统：微信小程序与 PC Web 长期并存，共用一套部署在独立服务器上的后端

## 2. 已确认需求

- Web 和小程序都提供匿名答题；昵称可选，不注册账号。
- 同一设备可在 24 小时内恢复未完成答题；提交后不可重复提交。
- Web 完整覆盖昵称、难度选择、答题、评分、错题解析和全部管理功能。
- Web 新增管理员维护的"嵌字笔记"；小程序暂不增加。
- 管理员有多个独立账号、权限相同；小程序和 Web 使用同一组账号密码。
- 管理员账号只通过服务器命令新增、改密、停用和恢复，不提供后台账号管理页面。
- 题目在 PC Web 上逐题录入；管理端同时支持题库 JSON 批量导入/导出，不做 Excel/ZIP 导入。
- 管理端选择题图后由 FastAPI 使用服务器侧 Cloudflare R2 凭据上传；数据库只保存返回的公开 HTTPS 图片直链。
- 本阶段不迁移旧云数据；新 SQLite 从空库开始，旧云数据继续保留且不删除。
- 预计同时在线约 10 人、每日提交几十次、题库几百题。
- 提交记录暂时永久保留；业务表不保存用户 IP。
- 服务器为阿里云香港 Ubuntu 22.04、4GB 内存，已有 Nginx，不使用 Docker。
- 使用已完成 ICP 备案的域名中转小程序/API 请求。
- SQLite 每日生成本地一致性备份并同步到阿里云 OSS。

## 3. 决策摘要

采用一个 Vue 单页应用、一个 FastAPI 单体服务、一个 SQLite 数据库文件：

| Layer | Choice | Decision |
| --- | --- | --- |
| Web | Vue 3 + TypeScript + Vite | 公开端自定义 UI，管理端适合表单与宽屏布局 |
| Web routing | Vue Router | 同一工程承载公开端和管理端两套 layout |
| Admin UI | Element Plus，按需导入 | 复用表单、表格、分页和对话框，不影响公开端视觉 |
| Client state | Vue composables + local state | 首版不引入 Pinia；状态规模不足以证明额外依赖必要 |
| HTTP client | Native `fetch` | 首版不引入 Axios |
| Backend | FastAPI + Uvicorn | 类型清晰、API 文档和测试方便，符合 Python 技术偏好 |
| ORM | SQLAlchemy 2.x sync | 使用成熟同步 ORM；当前规模不需要 async database stack |
| Schema migration | Alembic | 数据库结构变更可审计、可重复执行 |
| Database | SQLite, WAL mode | 单机、低并发、读多写少的长期正式方案 |
| Password hashing | `pwdlib[argon2]` | 只保存 Argon2 密码哈希 |
| Process | systemd + Python venv | 不使用 Docker，复用 Ubuntu 与现有 Nginx |
| Backup | SQLite online backup + OSS | 生成一致性快照后再异地保存 |

Vue 官方工具链使用 Vite 构建生产 `dist`；FastAPI 官方安全文档推荐 `pwdlib` 的 Argon2；SQLite WAL 允许读写并行，但要求数据库进程位于同一主机：

- [Vue Quick Start](https://vuejs.org/guide/quick-start.html)
- [FastAPI password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [SQLite WAL](https://www.sqlite.org/wal.html)
- [SQLite Online Backup API](https://www.sqlite.org/backup.html)
- [Alembic documentation](https://alembic.sqlalchemy.org/en/latest/)

## 4. 明确不采用的方案

- PostgreSQL：当前没有多实例、高写入并发或复杂分析需求，增加数据库运维没有收益。
- Redis：没有跨实例会话、队列或高频共享限流需求；Nginx 与 SQLite 足够。
- Docker：用户选择以现有 Nginx、venv、systemd 维护，容器不是当前前置条件。
- 微服务：题库、答题、管理和提交属于一个小型事务边界，拆分只会增加发布和故障面。
- Nuxt/SSR：产品不依赖搜索引擎收录或服务端渲染；Vite SPA 足够。
- Django Admin：能快速生成 CRUD，但无法直接满足已确认的品牌化答题端和“表单 + 实时预览”管理体验，最终仍需维护两套 UI。
- 动效库、Pinia、Axios、Celery：当前功能可由平台能力、Vue 和标准库覆盖，先不引入。
- 第三方验证码：首版使用请求限流和一次性答题会话；遭遇真实机器人流量后再选大陆可达的验证码服务。

## 5. 部署拓扑

```text
PC Web ─────────────┐
                    ├─> 已备案 HTTPS 域名/中转 ─> 香港 Nginx（正式部署时）
微信小程序 ─────────┘                              ├─> Vue dist
                                                   └─> /api -> Uvicorn/FastAPI
                                                                  ├─> SQLite
                                                                  └─> 坚果云公开 HTTPS 图片 URL

SQLite ─> 本地在线备份快照 ─> 阿里云 OSS
```

推荐使用同一对外域名：

```text
https://quiz.example.com/       Vue 静态页面
https://quiz.example.com/api/   FastAPI API
```

这样 Web 不需要 CORS；小程序只需配置一个合法 HTTPS 通讯域名。微信官方要求服务器域名经过 ICP 备案、使用有效 HTTPS 证书且不能直接使用 IP：[小程序网络使用说明](https://developers.weixin.qq.com/miniprogram/dev/framework/ability/network.html)。

### 5.1 代理边界

- 备案中转层必须传递真实客户端 IP 和原始协议。
- 香港 Nginx 只信任明确的中转服务器 IP；先覆盖客户端伪造的 `X-Forwarded-For`，再写入可信链。
- TLS 在对外域名有效；中转到香港也应使用 TLS 或受控私网链路。
- `/api/health` 只返回服务状态和数据库可连接性，不返回版本密钥、路径或用户数据。
- FastAPI 只监听 `127.0.0.1:8000`，不直接暴露公网端口。

## 6. 建议目录

在迁移完成前保留现有 `miniprogram/` 和 `cloudfunctions/`，新增代码集中在 `web/`：

```text
web/
  frontend/
    src/
      layouts/
      pages/
      components/
      composables/
      pages/admin/AdminFontReferencesPage.vue
      styles/tokens.css
  backend/
    app/
      main.py
      api/
      models.py
      schemas.py
      database.py
      services/
      admin_cli.py
    alembic/
    tests/
  scripts/
    migrate_cloud_export.py
    backup_sqlite.py
    sync_worker.py
  deploy/
    nginx.conf.example
    quiz-api.service
    quiz-backup.service
    quiz-backup.timer
    quiz-sync.service
    quiz-sync.timer
```

约束：

- Python 遵循 PEP 8；需要说明的公共函数使用 Google 风格 docstring。
- TypeScript 为 Web 默认语言，不新增 JavaScript 业务文件。
- 函数不超过 50 行；先复用平台和依赖能力，不创建 repository/base-service 等未被需求证明的抽象层。
- 管理员 CLI 使用标准库 `argparse`，不为四个命令引入额外 CLI 框架。

## 7. 数据模型

### 7.1 `questions`

| Field | Notes |
| --- | --- |
| `id` | 整数或 UUID 主键；迁移时另存旧云 `_id` 便于审计 |
| `text` | 题干，非空，最长 500 字符 |
| `image_url` | 可空 HTTPS URL；替代 `imageFileID` |
| `difficulty` | 1–5 |
| `option_a` … `option_d` | 四个非空选项 |
| `answer` | A/B/C/D |
| `explanation` | 统一解析，非空，最长 1000 字符 |
| `created_at`, `updated_at` | UTC 时间 |

不另建 options 表：选项固定为四个，拆表只增加查询与编辑复杂度。

### 7.2 `quiz_settings`

- 单例行，保存每次题数、三种模式的五档权重和字体快捷项。
- 权重可以保存为明确列或 JSON；选择 JSON 时必须通过 Pydantic 和数据库写入口验证结构。
- 题数范围 1–50；每种模式至少一个权重大于 0。

### 7.3 `admins` and `admin_sessions`

`admins` 保存用户名、密码哈希、启用状态和时间戳。`admin_sessions` 保存：

- 随机令牌哈希，不保存明文令牌。
- 管理员 ID、过期时间、创建时间和撤销时间。
- 默认 8 小时有效；管理员停用后其未过期会话立即失效。

CLI 必须支持：

```text
python -m app.admin_cli add USERNAME
python -m app.admin_cli password USERNAME
python -m app.admin_cli disable USERNAME
python -m app.admin_cli enable USERNAME
```

`disable` 拒绝停用最后一个有效管理员。首版不实现硬删除，避免破坏历史关联。

### 7.4 `quiz_attempts`

- 保存模式、抽中的题目 ID 顺序、创建时间、24 小时过期时间和提交状态。
- 创建时返回高熵 `attempt_token`；客户端只把令牌保存在本机存储，不创建额外设备指纹。
- 服务端保存令牌哈希；恢复和提交时客户端通过请求头携带令牌。
- 未完成答案先保存在客户端；服务端负责恢复题目集合和最终评分边界。
- 提交操作在单个事务内验证未过期/未提交、评分、写提交记录并封存 attempt。

这同时解决当前实现的评分边界问题：现在取题使用随机子集，但提交阶段将整个题库传入评分函数，见 [`../cloudfunctions/quiz/index.js`](../cloudfunctions/quiz/index.js) 的 `getQuestions` 与 `submit` 分支。新系统必须只评分 attempt 绑定的题目。

### 7.5 `submissions` and `submission_answers`

`submissions` 保存昵称、难度模式、分数、答对数、总题数和提交时间；不保存 IP。`submission_answers` 保存每题：

- 题目 ID。
- 用户选择。
- 是否正确。
- 提交时正确答案与解析快照。

保存快照可避免管理员以后修改题目后，历史记录显示与当时评分不一致。

提交记录永久保留，管理 API 必须分页，不允许无上限返回全部记录。

### 7.6 完整与设置配置传输

管理配置采用一个 versioned manifest，而不是依赖本机整数 ID。manifest 通过 `scope` 区分完整配置和设置配置：

```json
{
  "format": "mikanquiz-admin-config",
  "version": 1,
  "scope": "full",
  "exported_at": "...",
  "option_catalog": {"groups": [...]},
  "questions": [...],
  "settings": {...},
  "font_references": {"sections": [...], "unassigned_cards": [...]}
}
```

分区、字体、题目、笔记分区和笔记卡片均带持久化 `config_key`；题目通过 `correct_option_key` 引用字体。`exported_at` 仅用于传输展示，canonical projection 会移除它，再以 `ensure_ascii=false`、`sort_keys=true`、紧凑分隔符和 UTF-8 SHA-256 生成预览哈希。数据库整数 ID、时间戳和管理员凭据不进入该文件。

完整配置导入采用“预览 → hash-bound 确认 → replace”流程，替换题库、字体目录、策略和嵌字笔记；设置配置将 `scope` 设为 `settings`、不携带题目数据，采用 `mode: "settings"`，只更新字体目录、策略和嵌字笔记并保留当前题库。两种模式都不替换管理员、会话、attempt、提交历史，也不删除 R2 原始图片/字体。服务端在 `BEGIN IMMEDIATE` 中重新校验文件并重算当前哈希；完整配置还会检查活动 attempt，删除题目仍被未提交且未过期 attempt 引用时，整个导入返回 `ACTIVE_ATTEMPT_CONFLICT`。字体 URL 仅允许当前 R2 公共地址或 `QUIZ_FONT_SOURCE_ORIGINS` 中的 HTTPS origin，manifest 自身不能声明新信任来源。

导入提交后只在 `sync_outbox` 写入 `questions`/`notes` scope 任务。worker 短事务 claim、租约与 scope fence、网络发布、CAS 完成；每个 scope 单飞，失败按 1/5/30/300 秒退避，最多 10 次。任务会重建现有实体文件和全量快照，并携带删除 tombstone；租约丢失后，即使旧 worker 已写入对象，也会无条件重新排队当前 hash，避免晚到写覆盖新版本。

#### 单独题库 JSON 传输

配置迁移页还提供题库专项导入/导出，不参与完整配置的 `replace` 事务。`GET /api/v1/admin/questions/export` 返回 `version: 1` 的 `questions` 文件，包含题目内容、图片地址、难度、正确字体 ID、解析和审计时间；`POST /api/v1/admin/questions/import` 忽略题目 ID/时间字段，把有效题目追加到当前题库。已有题目不会覆盖或去重，重复导入同一文件会产生重复题目；字体 ID 不存在的条目单独失败，其余有效条目继续导入，并通过 `total`、`created`、`failed`、`errors` 返回结果。

## 8. API 边界

统一使用 `/api/v1`，响应使用稳定错误码和中文可显示消息。建议最小接口：

### 8.1 Public

```text
GET    /api/v1/quiz/settings
GET    /api/v1/font-references
POST   /api/v1/quiz/attempts
GET    /api/v1/quiz/attempts/current
POST   /api/v1/quiz/attempts/submit
```

- 创建 attempt 只返回清理后的题目，不返回答案和解析。
- 恢复需要 attempt token；过期返回明确状态，客户端清除本地令牌。
- 提交体只接受题目 ID → A/B/C/D；拒绝不属于该 attempt 的题目。
- 提交重试若已完成，返回同一次提交的稳定结果，不再新增记录。
- 退出答题不需要二次确认；客户端“重新开始”清除本地未完成进度后回到难度选择。

### 8.2 Authentication

```text
POST   /api/v1/admin/web/login
POST   /api/v1/admin/miniprogram/login
POST   /api/v1/admin/logout
GET    /api/v1/admin/session
```

- Web 登录设置 `HttpOnly; Secure; SameSite=Lax` cookie。
- 小程序登录返回一次可保存的 Bearer token。
- 两端使用同一账号密码和同一 `admin_sessions` 表，但令牌传输适配各平台。
- 登录失败使用一致响应和近似耗时，避免枚举用户名。

### 8.3 Admin

```text
GET    /api/v1/admin/questions?page=&query=&difficulty=
POST   /api/v1/admin/questions
GET    /api/v1/admin/questions/{id}
PATCH  /api/v1/admin/questions/{id}
DELETE /api/v1/admin/questions/{id}
GET    /api/v1/admin/settings
PUT    /api/v1/admin/settings/strategy
PUT    /api/v1/admin/settings/font-presets
GET    /api/v1/admin/submissions?page=&display_name=&from=&to=
GET    /api/v1/admin/submissions/{id}
GET    /api/v1/admin/config/export
GET    /api/v1/admin/config/export?scope=settings
POST   /api/v1/admin/config/import/validate
POST   /api/v1/admin/config/import
GET    /api/v1/admin/questions/export
POST   /api/v1/admin/questions/import
```

嵌字笔记卡片由 SQLite 的 `font_references` 表拥有。公开页通过 `GET /api/v1/font-references` 读取；管理员通过 `POST /api/v1/admin/font-references` 新增、`PATCH /api/v1/admin/font-references/{id}` 更新，通过 `DELETE /api/v1/admin/font-references/{id}` 删除。图片仍经受保护的 `/api/v1/admin/images` 上传。凭据绝不返回浏览器、写入数据库或提交到仓库。
- 后端以随机对象名写入配置目录，并返回由 `QUIZ_IMAGE_PUBLIC_BASE_URL` 组成的公开 HTTPS URL；管理表单自动填入并即时预览。
- Web 和小程序直接请求该公开直链；后端不代传图片，也不提供匿名文件上传 API。
- 当前不处理旧云存储图片，也不建立 `old_image_file_id -> new_image_url` 映射；恢复迁移时再单独制作并校验映射。

正式切换前，图片校验器必须确认：

1. 每个非空旧 `imageFileID` 都有唯一新 URL。
2. URL 使用 HTTPS，重定向次数受限。
3. 最终响应为允许的图片 `Content-Type`。
4. 链接不依赖短期签名或浏览器登录 cookie。
5. Web 浏览器和小程序真机都能显示。
6. 失败项阻止迁移完成，不静默清空图片。

## 12. 数据迁移与切换

本阶段不执行数据迁移或切换。旧云数据和旧小程序保持原状；新的 SQLite 仅保存新系统产生的数据。以下流程保留为未来迁移预案，未经项目方再次确认不得执行。

### 12.1 Dry run

1. 导出 `quiz_questions`、`quiz_settings`、`quiz_submissions` 和需要审计的旧管理员会话数据。
2. 上传全部题图并制作映射文件。
3. 对导出 JSON 做 schema 校验，不修改原文件。
4. 导入临时 SQLite。
5. 核对集合数、题目数、提交数、题图映射数和设置单例。
6. 对历史题目的 legacy `explanations` 取正确答案对应解析，转为统一 `explanation`。
7. 随机抽查题目、历史分数和提交答案；记录迁移耗时。
8. 运行新 API、Web 和小程序的只读冒烟测试。

#### 历史提交快照前置条件（阻塞项）

当前旧云函数写入 `quiz_submissions.answers` 的字段只有 `questionId`、`selected` 和 `isCorrect`；它不包含当时的题干、选项、正确答案、解析或图片 URL。管理员后来编辑题目后，不能安全地从当前题库反推出历史快照。

因此，`migrate_cloud_export.py` 只接受带完整不可变快照的提交导出，并会拒绝缺少顶层 `submittedAt`、`score`、`correctCount`、`total`，或每题缺少 `questionId`、`selected`、`isCorrect`、`correctAnswer`、`questionText`、`options`、`explanation` 的记录（脚本同时接受对应 snake_case 别名）；历史没有图片时 `imageUrl` 可以为空，但提供时必须是 HTTPS URL。正式迁移“全部提交记录”前，项目方必须提供可信的历史快照补充导出；不能用当前题目回填。若无法提供，必须在维护窗口前书面确认允许的降级策略（例如仅导入汇总分数，或不导入该批历史记录），再调整迁移方案与对账口径。

### 12.2 Production cutover

1. 公告维护窗口，停止旧小程序写入。
2. 对旧云数据做最终导出并保存只读副本。
3. 在线备份当前目标 SQLite；如为首次上线则保存空库基线。
4. 执行最终图片映射校验和导入。
5. 运行 Alembic 当前版本检查、数据库 `integrity_check` 和数量对账。
6. 启动 FastAPI，验证 `/api/health` 和核心 API。
7. 发布 Vue，并切换备案中转和小程序 API 地址。
8. 完成 Web 答题、Web 管理、小程序真机答题和小程序管理冒烟。
9. 保留旧云数据库只读，不立即删除。

### 12.3 Rollback

- 切换失败时停止新 API 写入，把小程序请求切回旧云函数。
- 保存失败期间的新 SQLite 和日志用于对账，不覆盖旧云数据。
- 因为没有双写，正式开放新系统后若已有真实提交，回滚需要先导出这些新增提交并明确后续补录策略。

## 13. 备份与恢复

每日由 systemd timer 执行：

1. 使用 Python 标准库 `sqlite3.Connection.backup()` 或 SQLite `.backup` 生成一致性快照。
2. 对快照执行 `PRAGMA integrity_check`。
3. 压缩并写入日期、schema revision 和校验和。
4. 保留最近 7 个每日备份和 4 个每周备份。
5. 使用阿里云 `ossutil` 上传 OSS；上传成功后才进入本地轮换。
6. 上传失败退出非零并进入 journald，不能误报成功。

至少每季度执行一次恢复演练：在临时目录恢复、检查 Alembic revision、运行 `integrity_check`、启动只读测试实例并抽查题目与提交。只验证“OSS 中有文件”不算恢复成功。

## 14. 运行与发布

- Python 使用 Ubuntu 支持的 3.10+ 运行时和项目 venv；生产依赖锁定确切版本。
- systemd 以独立低权限用户运行 API，环境变量文件权限 `0600`。
- Uvicorn 单 worker 监听 `127.0.0.1:8000`。
- Vue `npm run build` 产物部署到版本化目录，再原子切换 Nginx 指向的软链接。
- 后端发布顺序：备份 → 安装锁定依赖 → `alembic upgrade head` → 重启 systemd → health check。
- 结构化日志输出到 stdout/journald；首版不引入 Sentry、Prometheus 或 ELK。
- Nginx 与应用日志轮换；管理员登录失败只记录必要字段，不记录密码、会话令牌或答案内容。

## 15. 验证门槛

### Backend deterministic checks

- 选题权重、题数不足和随机不重复。
- attempt 24 小时过期、恢复、一次性提交与幂等重试。
- 只评分 attempt 题目，拒绝额外题目和非法选项。
- 分数、错题解析和历史快照正确。
- 题目/设置边界校验。
- Argon2 登录、停用账号、会话过期和最后管理员保护。
- SQLite 临时库上的 Alembic 从空库升级与迁移数据导入。
- 使用录制的实际请求证明匿名 API 不返回答案。

最小可执行命令目标：

```sh
python -m pytest web/backend/tests
npm --prefix web/frontend run build
```

### Manual release smoke

- Web：首页 → 选难度 → 答完 → 提交 → 查看错题 → 再答一次。
- Web：刷新后恢复 24 小时内未完成 attempt；已提交 attempt 不重复写记录。
- Web：管理员登录、题目 CRUD、策略、字体快捷项、分页提交记录。
- Web：管理员导出完整 JSON（含题库）或设置 JSON（不含题库），选择文件后按两步流程预览 hash/差异，并在明确确认后应用对应范围。
- Web：管理员在同一配置迁移页下方的题库工具导出题库 JSON，选择题库文件追加导入，并查看成功/失败统计。
- Sync：运行 outbox worker，验证 R2 发布失败可重试且不会阻塞 API 写入。
- Web：嵌字笔记、图片放大、图片失败状态。
- 小程序：同一后端上的公开答题和账号密码管理登录。
- Network：备案域名、TLS 证书链、真实 IP 转发、限流响应和图床可达性。
- Backup：生成快照、上传 OSS，并从该对象恢复到临时库。

UI 验收维度见 [`../DESIGN.md`](../DESIGN.md) 的 Accessibility、Responsive behavior 与 Implementation constraints。

## 16. 分阶段实施

### Stage 1 — Backend foundation

- 建立 SQLAlchemy schema、Alembic、管理员 CLI、认证、题库/设置 API。
- 实现 attempt 边界、评分、提交记录和 deterministic tests。
- 结果门槛：临时 SQLite 上后端测试通过，API 不依赖微信上下文。

### Stage 2 — PC Web

- 按 `DESIGN.md` 实现公开答题、管理端和嵌字笔记卡片。
- 结果门槛：构建通过；1440px/1024px/键盘/减少动态效果的视觉与功能验收通过。

### Stage 3 — Mini Program adapter

- 将 `wx.cloud.callFunction` 替换为统一的 API client。
- 把管理员认证改为账号密码，把图片字段改为 HTTPS URL。
- 结果门槛：真机通过备案域名完成答题、提交与管理登录。

### Stage 4 — Migration rehearsal（暂缓）

- 完成云数据导出、图片映射、导入、对账、备份和恢复演练。
- 结果门槛：所有题目图片可用，记录数量一致，迁移脚本对缺失映射失败退出。

### Stage 5 — Cutover（暂缓）

- 在维护窗口执行最终迁移和域名切换。
- 结果门槛：Web、小程序、管理端、限流和 OSS 恢复冒烟全部通过；旧云数据保留只读。

## 17. 待确认但不阻塞编码的事项

- 坚果云公开直链的稳定格式、是否存在登录/防盗链限制，以及 Web 与小程序真机可达性。
- 正式域名、中转服务器地址、真实 IP header 约定和 TLS 终止位置。
- 嵌字笔记首批静态图片清单。
- 阿里云 OSS bucket、凭证注入方式和生命周期策略。

这些事项不得通过硬编码 R2 密钥或猜测 URL 格式绕过；实现应保留明确配置点，并在正式迁移或生产部署前完成验证。
