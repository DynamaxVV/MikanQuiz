# 本地运行 Web 与独立后端

当前 Web 是主要开发路径。本地阶段不需要 Nginx 或域名；后端使用本地 SQLite，前端开发服务器自动将 `/api` 转发到后端。旧小程序客户端与云函数保留为停止维护的历史代码，不属于 Web 运行路径。

## 一条命令启动前后端

首次准备好后端虚拟环境、依赖和前端依赖后，在 `web/` 目录执行：

```sh
npm run dev
```

该命令会先执行数据库迁移、启动 FastAPI（`127.0.0.1:8000`），再启动 Vite。按 `Ctrl+C` 会同时停止两者。

## 首次准备

从仓库根目录执行：

```sh
cd web/backend
cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
mkdir -p var
export QUIZ_DATABASE_URL="sqlite:///$(pwd)/var/quiz.db"
export QUIZ_COOKIE_SECURE=false
alembic upgrade head
python -m app.admin_cli add operator
```

管理员命令会交互式要求设置密码。数据库文件在 `web/backend/var/quiz.db`，不包含旧云数据。

```sh
cd ../frontend
npm ci
```

在浏览器打开 Vite 输出的本地地址（通常为 `http://localhost:5173`）。管理员入口为 `/admin/login`。

## 站点配置

在 `web/frontend` 执行 `cp .env.example .env.local` 后编辑：

| 变量 | 用途 |
| --- | --- |
| `VITE_SITE_GROUP_NAME` | 首页招募名称；留空隐藏整个招募区域 |
| `VITE_SITE_GROUP_DESCRIPTION` | 招募说明 |
| `VITE_SITE_JOIN_GROUP` | 加入群号；留空隐藏 |
| `VITE_SITE_CHAT_GROUP` | 闲聊群号；留空隐藏 |
| `DEV_ALLOWED_HOSTS` | 开发服务器额外允许的域名，逗号分隔；本机访问无需设置 |
| `DEV_API_TARGET` | 开发代理后端，默认 `http://127.0.0.1:8000` |

`VITE_*` 会在构建时写入浏览器文件，不能放密钥。修改站点信息后需重新构建；`.env.local` 不提交。`VITE_DEV_API_TARGET` 保留为旧开发配置的兼容项，新配置使用 `DEV_API_TARGET`。

首次环境准备完成后，在 `web/` 执行 `npm run dev`。示例后端 `.env` 使用 local 图片存储，数据库初始为空；先登录管理端配置字体与题目。生产使用 R2 时将 `QUIZ_STORAGE_BACKEND` 改为 `r2` 并填写对应配置。

## 答题与嵌字笔记

- 昵称可选；不填写也能开始和提交答题。
- 未完成答题会在同一设备保留 24 小时。退出答题不需要确认；“重新开始本次练习”会清除本地进度并返回难度选择。
- 嵌字笔记卡片由管理员在“嵌字笔记管理”页面上传、添加标题/说明/难度或编辑/删除；公开页从 SQLite 读取，支持按星级筛选和标题搜索。

## 配置与题库迁移

登录管理端后打开 `/admin/config`。右上角的“导出全部配置”用于备份和恢复题库、字体分区、出题设置与嵌字笔记，导入前必须完成只读预览并确认替换；管理员账号、答题会话和提交历史不会被替换。

第一步也可以点击“导出设置配置”，生成不含题库的 `mikanquiz-admin-settings.json`。导入设置配置只更新字体分区、出题设置和嵌字笔记，当前题库保持不变；页面会在第二步明确显示“设置配置 · 保留题库”。

第二步完成校验后，页面下方的“题库导入与导出”工具用于日常批量维护：点击“导出题库 JSON”下载当前题库，选择同格式文件后点击“追加到当前题库”。独立导入只追加题目，不覆盖或去重已有题目；页面会显示读取、新增和未导入数量以及失败原因。不要重复导入同一文件，除非确实需要复制题目。

## 图片存储与上传

后端启动时默认读取 `web/backend/.env`。后端未配置存储方式时默认使用 Cloudflare R2；示例 `.env` 为便于本地复现已选择 local 模式。本地开发可使用 `QUIZ_STORAGE_BACKEND=local`，把文件写入本地目录。若首次准备时还未复制示例文件，先复制，再填入实际值（`.env` 已被忽略，不能提交到仓库）：

```sh
cd web/backend
cp .env.example .env
```

R2 模式需要填写 `QUIZ_R2_ENDPOINT`、`QUIZ_R2_ACCESS_KEY_ID`、`QUIZ_R2_SECRET_ACCESS_KEY`、`QUIZ_R2_BUCKET` 与 `QUIZ_R2_PUBLIC_BASE_URL`。后者是绑定到 R2 bucket 的自定义 HTTPS 域名。进程环境变量优先于 `.env`。本地模式使用 `QUIZ_LOCAL_STORAGE_PATH` 和 `QUIZ_LOCAL_PUBLIC_BASE_URL`，只适合开发，不应把上传目录直接暴露到公网。

R2 模式首次运行还需安装官方 AWS SDK：`cd web/r2-uploader && npm install`。管理端选择图片后，FastAPI 调用本地 Node 适配器，以 AWS SDK v3 写入 R2，并返回自定义域名外链；密钥不会进入浏览器。本地模式不需要该适配器。

## 本地检查

从仓库根目录执行：

```sh
(cd web/backend && .venv/bin/python -m pytest tests -q)
npm --prefix web/frontend run test:api-contract
npm --prefix web/frontend run test:batch-core
npm --prefix web/frontend run build
```

正式上线、Nginx、HTTPS、备份恢复及日常更新见 [部署与维护手册](deploy/README.md)。
