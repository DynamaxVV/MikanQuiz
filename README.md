# MikanQuiz

<p align="center">
  <img src="web/frontend/src/assets/mascot-study-with-bg.png" alt="MikanQuiz Web 首页插画" width="360">
</p>

砂糖的秘密小课堂：面向汉字与字体学习的 Web 答题系统，使用 Vue 3、FastAPI 和 SQLite。支持匿名答题、字体预览、错题解析、嵌字笔记，以及管理员批量制题和配置导入导出。

## 功能介绍

### 答题练习

- 无需注册即可开始答题，昵称可选，按难度选择练习内容。
- 对照题图辨认汉字字体；答题时可预览字体，提交后查看结果和题目解析。
- 同一设备会暂存未完成的答题进度，方便稍后继续。

### 嵌字笔记

- 浏览公开的嵌字资料，按难度筛选或搜索标题。
- 查看资料配图并下载对应 PDF。

### 管理后台

- 筛选、查看和编辑题目，也可以从漫画页面批量框选题图、连续制题和分批入库。
- 管理员可维护字体分区、快捷字体项、出题策略、嵌字笔记和 PDF 资料。
- 查看答题提交与题库统计；支持题库 JSON 导入导出，以及带校验预览的完整配置备份与恢复。
- 批量制题草稿保存在当前浏览器，可在页面刷新后继续编辑；正式入库时才上传裁切后的题图。

## 技术栈

| 部分 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Vue Router；管理界面使用 Element Plus，答题页面为自定义 UI |
| 后端 | Python、FastAPI、SQLAlchemy、Alembic |
| 数据库 | SQLite（WAL），数据库结构通过 Alembic 迁移管理 |
| 字体处理 | FontTools、Brotli；提供题目字体预览与字体资料 |
| 图片存储 | 开发环境可使用本地存储；生产环境使用 Cloudflare R2 和 Node.js AWS SDK 适配器 |
| 部署 | Nginx、systemd；部署、备份和维护说明见下文手册 |

## 界面预览

### 首页

<p align="center">
  <img src="docs/images/readme-home.png" alt="MikanQuiz Web 首页" width="960">
</p>

### 管理页

<p align="center">
  <img src="docs/images/readme-admin.png" alt="MikanQuiz Web 管理页" width="960">
</p>

## 项目组成

| 目录 | 用途 |
| --- | --- |
| `web/frontend/` | Vue 3 + TypeScript + Vite 前端 |
| `web/backend/` | FastAPI + SQLite 后端与 Alembic 迁移 |
| `web/r2-uploader/` | Cloudflare R2 上传与删除适配器 |
| `web/deploy/` | Nginx、systemd 与定时任务部署示例 |
| `web/scripts/` | 本地启动、数据库备份、过期会话清理与 R2 同步工具 |

旧微信小程序和云函数仍保留为历史代码，**停止维护，不属于当前运行与发布路径**：

| 历史目录 | 状态 |
| --- | --- |
| `miniprogram/` | 旧微信小程序，详见 [历史客户端说明](miniprogram/README.md) |
| `cloudfunctions/quiz/` | 旧云函数，详见 [历史云函数说明](cloudfunctions/quiz/README.md) |
| 根目录 `project.config.json` | 旧微信小程序开发者工具配置，非 Web 依赖 |

## 本地运行

需要 Python 3.10+、Node.js 22.18+ 和 npm。以下命令从仓库根目录依次执行：

```sh
cd web/backend
cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
mkdir -p var
alembic upgrade head
python -m app.admin_cli add operator

cd ../frontend
npm ci
cp .env.example .env.local

cd ..
npm run dev
```

管理员命令会交互式设置密码。浏览器访问 Vite 输出的地址（通常为 `http://localhost:5173`），管理入口为 `/admin/login`。

示例后端配置使用本地 SQLite 和 local 图片存储，不需要 R2 凭据。首次启动没有题库，请在管理端配置字体、创建题目或导入自己的配置。已有 `.env` 或 `.env.local` 时编辑现有文件，不要覆盖。local 存储仅供开发；生产环境使用 R2 和 HTTPS。

## 站点与部署配置

**服务器部署入口：[Web 部署与维护手册](web/deploy/README.md)**，包含首次部署、HTTPS、日常更新、备份恢复、字体缓存预热和常见故障排查。

前端 `.env.local` 可配置首页招募名称、说明、群号及开发域名；未配置招募名称时隐藏该区域。变量说明见 [Web 使用说明](web/README.md#站点配置)。`VITE_*` 是构建时公开配置，不能填写凭据。

生产数据库、R2 和 SMTP 通过后端环境变量配置，详见 [后端说明](web/backend/README.md)。生产构建使用 `npm --prefix web/frontend run build`；部署所需的 `web/frontend/dist/` 保留在仓库中。构建前应准备目标站点的前端配置。

## 检查

从仓库根目录执行：

```sh
(cd web/backend && .venv/bin/python -m pytest tests -q)
npm --prefix web/frontend run test:api-contract
npm --prefix web/frontend run test:batch-core
npm --prefix web/frontend run build
```

浏览器回归测试使用 Playwright 自动生成的合成图片，不需要私人漫画资料，安装 Chromium 和启动命令见 [批量制题验证说明](docs/BATCH_QUESTIONS_ZH.md#可重复验证)。

本地素材、数据库、环境文件、诊断导出和私人工作笔记不提交。完整使用说明见 [web/README.md](web/README.md)，设计说明见 [DESIGN.md](DESIGN.md)。
