# MikanQuiz

![MikanQuiz Logo](mikanquiz_logo.png)

砂糖的秘密小课堂：一套面向汉字与字体学习的答题系统，包含微信小程序、Web 端和共用的 FastAPI 后端。

## 项目组成

| 目录 | 用途 |
| --- | --- |
| `miniprogram/` | 微信小程序：练习、答题与管理入口 |
| `cloudfunctions/quiz/` | 小程序云函数 |
| `web/frontend/` | Vue 3 + Vite Web 前端 |
| `web/backend/` | FastAPI + SQLite 共用后端 |
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

## 微信小程序

使用微信开发者工具打开项目根目录。配置已指定小程序目录为 `miniprogram/`、云函数目录为 `cloudfunctions/`。如需连接独立后端，请按部署环境修改小程序 API 配置，并将域名加入微信小程序的合法请求域名。

## 检查

```sh
cd miniprogram && npm run check
cd web/backend && .venv/bin/python -m pytest tests -q
cd web/frontend && npm run test:api-contract && npm run build
```

详细的 Web 使用说明见 [web/README.md](web/README.md)，服务端接口与部署说明见 [web/backend/README.md](web/backend/README.md)。
