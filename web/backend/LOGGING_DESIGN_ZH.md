# 后端日志设计

## 目标与边界

本设计为 FastAPI 单体服务提供可通过 SSH 事后排障的日志能力，覆盖：

- 线上接口报错与未处理异常；
- 管理员操作追溯；
- 答题流程中的业务异常；
- Cloudflare R2 图片上传故障；
- 恶意或异常访问；
- **每个 API 请求的真实用户 IP**。

服务部署在单个 Uvicorn worker、宿主机 Nginx 和 systemd 之后。日志不接入 Loki、ELK、Sentry 等外部平台，不新增 Python 依赖，不新增数据库表，也不改变 API 响应契约。

## 总体方案

应用使用 Python 标准库 `logging`，将单行 JSON 输出至 stdout。systemd 收集 stdout/stderr，journald 负责索引与轮转；应用自身不写日志文件。

```text
浏览器 / 小程序
       |
       v
     Nginx -- X-Forwarded-For --> Uvicorn / FastAPI -- JSON stdout --> systemd-journald
       |                                                                  |
       +---------------- Nginx access/error log                           +--> journalctl
```

应用关闭 Uvicorn 原生 access log，避免产生一份无 `request_id` 的重复文本日志。Uvicorn 的启动和错误日志也使用同一个 JSON formatter。

## 用户 IP 的可信来源（强制）

记录 IP 的字段名为 `client_ip`，它必须是经过受信任反向代理处理后的真实用户地址。

1. Uvicorn 仅监听 `127.0.0.1`，禁止直接暴露公网端口。
2. Nginx 必须向上游传递：

   ```nginx
   # 覆盖客户端伪造的值；$remote_addr 已由 real_ip 配置还原为可信地址。
   proxy_set_header X-Forwarded-For $remote_addr;
   proxy_set_header X-Real-IP $remote_addr;
   ```

3. Uvicorn 必须带以下参数启动：

   ```sh
   --proxy-headers --forwarded-allow-ips=127.0.0.1
   ```

4. 应用从 `request.client.host` 读取 `client_ip`，依赖上述 Uvicorn 信任链还原地址；不直接解析任意来源的 `X-Forwarded-For`。

这样，来自公网的伪造 `X-Forwarded-For` 不会被信任。若将来 Nginx 与应用分离到不同主机，`--forwarded-allow-ips` 必须改为 Nginx 的固定内网 IP，不能改成 `*`。

## 日志格式与隐私边界

所有应用日志为一行 JSON，公共字段如下：

```json
{
  "timestamp": "2026-07-23T09:12:34.567+00:00",
  "level": "INFO",
  "event": "http_request",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

每个 API 请求由中间件生成新的 UUID v4 `request_id`，通过 `X-Request-ID` 响应头回传。不得使用客户端提供的 ID，避免日志注入和跨请求混淆。

允许记录：管理员用户名、答题昵称、`client_ip`、`user_agent`、HTTP 方法、无查询串的路径、路由模板、状态码、耗时、资源 ID、分数和稳定业务错误码。

严禁记录：密码、Cookie、Bearer token、`X-Quiz-Attempt`、任何完整请求/响应体、答题答案、题目答案、R2 密钥、上传文件内容、原始 R2 子进程 stdout/stderr。请求 URL 仅记录 path，不记录 query string。

## 事件模型

### 请求与异常

每个 `/api` 请求产生 `http_request`：

```json
{
  "event": "http_request",
  "request_id": "...",
  "method": "POST",
  "path": "/api/v1/quiz/attempts/submit",
  "route": "/api/v1/quiz/attempts/submit",
  "status_code": 200,
  "duration_ms": 84,
  "client_ip": "203.0.113.8",
  "user_agent": "Mozilla/5.0 ..."
}
```

`/api/health` 的成功请求不记 access log，失败仍记录。预期的 `ApiError` 或校验失败额外产生 `api_error`，携带 `status_code` 和稳定的 `error_code`；未处理异常产生 `unhandled_exception`，携带异常类型和 traceback。两类事件均使用相同 `request_id`。

### 安全与管理员审计

| 事件 | 记录字段 |
| --- | --- |
| `admin_login_succeeded` | `admin_username`、`client_ip`、`user_agent` |
| `admin_login_failed` | 输入的 `admin_username`、`client_ip`、`user_agent` |
| `admin_session_invalid` | `client_ip`、`user_agent`、稳定失败码 |
| `admin_logout` | `admin_username`、`client_ip` |
| `question_created/updated/deleted` | `admin_username`、`question_id` |
| `option_catalog_replaced` | `admin_username`、选项组/选项数量 |
| `strategy_updated` | `admin_username`、题目数和难度权重摘要 |
| `font_reference_created/deleted` | `admin_username`、`reference_id` |

登录失败、无效会话和所有 4xx/5xx 的 access event 都保留 `client_ip` 与 `user_agent`，供排查异常访问。

### 答题与 R2

| 事件 | 记录字段 |
| --- | --- |
| `quiz_attempt_created` | 模式、抽题数、匿名 attempt 数据库 ID、`client_ip` |
| `quiz_submitted` | 提交 ID、昵称、模式、分数、正确数、总题数、`client_ip` |
| `quiz_submission_replayed` | 提交 ID、匿名 attempt ID、`client_ip` |
| `quiz_business_error` | 稳定业务错误码、可获得的匿名资源 ID、`client_ip` |
| `r2_upload_succeeded` | 管理员用户名、MIME 类型、字节数、耗时、`client_ip` |
| `r2_upload_failed` | 管理员用户名、MIME 类型、字节数、耗时、异常类别、`client_ip` |

R2 失败只记录 Python 异常类别（例如 `TimeoutExpired` 或 `CalledProcessError`），不得直接写入子进程输出，避免未来依赖输出包含敏感配置时泄露。

## 实施位置

- `app/logging.py`：JSON formatter、上下文变量、`configure_logging()` 和获取当前请求字段的 helper。
- `app/main.py`：应用创建时配置 logging，注册请求中间件、预期错误日志和兜底异常日志。
- `app/api.py`：在登录、登出和管理员写操作、答题创建/提交处记录审计或业务事件。
- `app/services/images.py`：在 R2 上传的成功与失败处记录安全的上传事件；不得写入上传器原始输出。
- `app/config.py`：可选的 `QUIZ_LOG_LEVEL`，默认 `INFO`，仅接受 `DEBUG`、`INFO`、`WARNING`、`ERROR`。
- `tests/`：以自定义内存 handler 或 `caplog` 验证 JSON 字段、关联 ID 和敏感字段缺失。

业务日志通过 `contextvars` 自动附带当前请求的 `request_id`、`client_ip` 和 `user_agent`；路由和服务只传业务字段，避免遗漏上下文或传递 token。

## systemd 与 journald

建议服务单元：

```ini
[Service]
SyslogIdentifier=mikan-quiz-api
StandardOutput=journal
StandardError=journal
ExecStart=/path/to/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --proxy-headers --forwarded-allow-ips=127.0.0.1
```

在 `/etc/systemd/journald.conf.d/mikan-quiz.conf` 配置：

```ini
[Journal]
SystemMaxUse=2G
MaxRetentionSec=7day
```

这两个限制作用于整台服务器的 system journal，而非本服务独占。如果同机还有大量高频日志，应用日志可能早于 7 天被淘汰；当前单服务、INFO 级别运行的部署假设下满足目标。

修改后由运维执行：

```sh
sudo systemctl restart systemd-journald
sudo systemctl daemon-reload
sudo systemctl restart mikan-quiz-api
```

## 排障命令

```sh
# 最近一小时
journalctl -u mikan-quiz-api --since "1 hour ago" -o cat

# 单个请求的完整链路
journalctl -u mikan-quiz-api -o cat |
  jq -c 'select(.request_id == "请求ID")'

# 未处理异常和 R2 上传失败
journalctl -u mikan-quiz-api -o cat |
  jq -c 'select(.event == "unhandled_exception" or .event == "r2_upload_failed")'

# 管理员操作
journalctl -u mikan-quiz-api --since today -o cat |
  jq -c 'select(.event | startswith("question_") or startswith("strategy_") or startswith("option_"))'

# 某个 IP 的异常访问
journalctl -u mikan-quiz-api --since today -o cat |
  jq -c 'select(.client_ip == "203.0.113.8" and (.status_code >= 400 or .event == "admin_login_failed"))'
```

## 验收标准

1. 正常 API 请求生成 JSON access event，响应中有 `X-Request-ID`，且 event 中有正确 `client_ip`。
2. Nginx 后真实访问的 IP 与应用日志一致；直接连接 Uvicorn 时不能伪造转发 IP。
3. `ApiError` 会记录稳定错误码，未处理异常会记录 traceback，二者可按 `request_id` 关联。
4. 管理员登录、题目改动、策略改动、R2 成功/失败、答题创建/提交均产生日志。
5. 测试断言日志中不含密码、Cookie、Bearer token、答题 token、答题答案或 R2 密钥。
6. `journalctl -u mikan-quiz-api -o cat` 可直接用 `jq` 按 JSON 字段查询。
