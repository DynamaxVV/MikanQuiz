# MikanQuiz

![MikanQuiz Logo](mikanquiz_logo.png)

砂糖的秘密小课堂：一套面向汉字与字体学习的答题系统。当前主产品是 Web 端，微信小程序保留为冻结的兼容客户端，后端由 FastAPI 提供。

## 项目组成

| 目录 | 用途 |
| --- | --- |
| `miniprogram/` | 冻结的微信小程序兼容客户端；当前代码通过独立 FastAPI API 适配器访问后端 |
| `cloudfunctions/quiz/` | 历史云函数实现，仅供旧数据迁移、回溯和兼容排查 |
| `web/frontend/` | Vue 3 + Vite Web 前端 |
| `web/backend/` | 当前主路径的 FastAPI + SQLite 后端；也保留小程序兼容 API |
| `web/r2-uploader/` | 管理端图片上传到 Cloudflare R2 的适配器 |

## 本地运行 Web 端

首次准备后端环境和前端依赖：

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

cd ../frontend
npm install
```

再从 `web/` 目录启动前后端：

```sh
cd ..
npm run dev
```

浏览器访问 Vite 输出的本地地址（通常为 `http://localhost:5173`），管理端入口为 `/admin/login`。

## 冻结的微信小程序

如需复现旧客户端，仍可使用微信开发者工具打开项目根目录；配置已指定小程序目录为 `miniprogram/`。当前小程序通过 `miniprogram/services/api.js` 请求独立 FastAPI 后端，新增功能和 UI 不再以小程序为开发目标。`cloudfunctions/quiz/` 仅作为历史实现和迁移参考，不属于当前 Web 本地运行路径。

冻结客户端只保留 `miniprogram/app.json` 注册的答题和管理页面。未注册的旧 `chatBot`、`foodBuy` 页面及其 `agent-ui`、`toolCard`、`page-nav` 支持组件已从当前工作树移除；如需复现这些功能，只能从历史提交恢复。

## 检查

从仓库根目录执行：

```sh
npm --prefix miniprogram run check
(cd web/backend && .venv/bin/python -m pytest tests -q)
npm --prefix web/frontend run test:api-contract
npm --prefix web/frontend run test:batch-core
npm --prefix web/frontend run build
```

详细的 Web 使用说明见 [web/README.md](web/README.md)，服务端接口与部署说明见 [web/backend/README.md](web/backend/README.md)。
