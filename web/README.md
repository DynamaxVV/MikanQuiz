# 本地运行 Web 与独立后端

当前阶段不需要 Nginx、域名或旧云数据迁移。后端使用本地 SQLite，前端开发服务器自动将 `/api` 转发到后端。

## 一条命令启动前后端

首次准备好后端虚拟环境、依赖和前端依赖后，在 `web/` 目录执行：

```sh
npm run dev
```

该命令会先执行数据库迁移、启动 FastAPI（`127.0.0.1:8000`），再启动 Vite。按 `Ctrl+C` 会同时停止两者。

## 首次准备

```sh
cd web/backend
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
cd web/frontend
npm install
```

在浏览器打开 Vite 输出的本地地址（通常为 `http://localhost:5173`）。管理员入口为 `/admin/login`。

## 答题与嵌字笔记

- 昵称可选；不填写也能开始和提交答题。
- 未完成答题会在同一设备保留 24 小时。退出答题不需要确认；“重新开始本次练习”会清除本地进度并返回难度选择。
- 嵌字笔记卡片由管理员在“嵌字笔记管理”页面上传、添加标题/说明/难度或编辑/删除；公开页从 SQLite 读取，支持按星级筛选和标题搜索。

## 图片上传到 Cloudflare R2

后端启动时默认读取 `web/backend/.env`。先复制示例文件，再填入实际值（`.env` 已被忽略，不能提交到仓库）：

```sh
cd web/backend
cp .env.example .env
```

在 `.env` 中填写 `QUIZ_R2_ENDPOINT`、`QUIZ_R2_ACCESS_KEY_ID`、`QUIZ_R2_SECRET_ACCESS_KEY`、`QUIZ_R2_BUCKET` 与 `QUIZ_R2_PUBLIC_BASE_URL`。后者是绑定到 R2 bucket 的自定义 HTTPS 域名。进程环境变量优先于 `.env`。

首次运行还需安装官方 AWS SDK：`cd web/r2-uploader && npm install`。管理端选择图片后，FastAPI 调用本地 Node 适配器，以 AWS SDK v3 写入 R2，并返回自定义域名外链；密钥不会进入浏览器。

## 本地检查

```sh
cd web/backend && .venv/bin/python -m pytest tests -q
cd web/frontend && npm run test:api-contract && npm run build
```

正式上线、Nginx、OSS 备份、备案域名与旧云数据迁移均另行执行；对应预案见 [`../docs/WEB_ARCHITECTURE_ZH.md`](../docs/WEB_ARCHITECTURE_ZH.md)。
