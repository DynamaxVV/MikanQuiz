# AGENTS.md

## Project Overview

MikanQuiz: Chinese character/font quiz system with a Vue 3 Web frontend and FastAPI backend.

## Legacy Miniprogram (Unmaintained)

The original `miniprogram/`, `cloudfunctions/quiz/`, and root `project.config.json` remain as historical code and configuration. They are unmaintained and are not part of the Web build or deployment. Unused cross-platform scaffolding and old cloud-export migration tooling have been removed. New features and fixes target `web/`; do not add miniprogram compatibility unless explicitly requested. See `miniprogram/README.md` and `cloudfunctions/quiz/README.md`. The backend's historical Bearer login API remains for existing integrations and tests.

## Directory Structure

- `web/frontend/` — Vue 3 + Vite Web frontend (TypeScript)
- `web/backend/` — FastAPI + SQLite backend (Python)
- `web/r2-uploader/` — Cloudflare R2 image upload adapter (Node.js)

## Development Commands

### Web (primary development)

```sh
# Start both backend + frontend (recommended)
cd web && npm run dev

# Backend only
cd web/backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend only
cd web/frontend && npm run dev
```

### First-time Backend Setup

```sh
cd web/backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
mkdir -p var
export QUIZ_DATABASE_URL="sqlite:///$(pwd)/var/quiz.db"
export QUIZ_COOKIE_SECURE=false
alembic upgrade head
python -m app.admin_cli add operator  # interactive password setup
```

### First-time Frontend Setup

```sh
cd web/frontend && npm install
```

### Verification Commands

```sh
# Backend tests
(cd web/backend && .venv/bin/python -m pytest tests -q)

# Frontend contract, batch core check and build
npm --prefix web/frontend run test:api-contract
npm --prefix web/frontend run test:batch-core
npm --prefix web/frontend run build
```

## Architecture Notes

- **Database**: SQLite with WAL mode, single Uvicorn worker, Alembic migrations (never `create_all()`)
- **API**: Business endpoints use the `/api/v1` prefix, JSON and snake_case fields; `/api/health` and `/api/docs` are infrastructure/documentation exceptions
- **Auth**: Web uses HttpOnly cookies; admin accounts managed via CLI only
- **Images**: Production defaults to Cloudflare R2. Local development can use `QUIZ_STORAGE_BACKEND=local`; the database stores the resulting public URL in either mode.
- **Image upload flow**: On the question editor page, selected/pasted images are held in the browser and shown as `blob:` previews. Upload to the configured backend happens together with question save, not immediately on selection. The save button shows a loading spinner and the form is disabled during save.

## Key Conventions

- Admin account management: `python -m app.admin_cli {add|list|password|disable|enable} USERNAME`
- Backend env vars: `QUIZ_DATABASE_URL`, `QUIZ_COOKIE_SECURE`, `QUIZ_ADMIN_SESSION_HOURS`
- Image storage: `QUIZ_STORAGE_BACKEND=r2|local`. R2 uses `QUIZ_R2_ENDPOINT`, `QUIZ_R2_ACCESS_KEY_ID`, `QUIZ_R2_SECRET_ACCESS_KEY`, `QUIZ_R2_BUCKET`, and `QUIZ_R2_PUBLIC_BASE_URL`; local development uses `QUIZ_LOCAL_STORAGE_PATH` and `QUIZ_LOCAL_PUBLIC_BASE_URL`.
- Backend reads `.env` from `web/backend/.env` at startup (process env vars take precedence)
- Frontend uses Element Plus only for admin UI; public quiz UI is custom
- Design tokens defined in `DESIGN.md`; follow warm color palette (#FFF9F0 background, #A94F1F action)
- API contract: all snake_case fields, `/api/v1` prefix, errors as `{"error":{"code":"...","message":"..."}}`
- Question import/export: JSON format with `{version: 1, questions: [...]}`. Export includes `id`, `created_at`, `updated_at`; import ignores them (extra fields allowed). Image URLs are stored as produced by the configured storage backend.
- When the user asks to commit or submit MikanQuiz changes to GitHub, include the requested source changes and the rebuilt `web/frontend/dist/` assets so a server-side `git pull` receives deployable frontend files. Preserve unrelated worktree changes.

## Common Pitfalls

- Backend must have `.venv` created and activated before running
- Database migrations must run before starting backend (`alembic upgrade head`)
- Web frontend proxies `/api` to backend in dev mode
- Local image storage is for development only; do not expose its upload directory as a production public store
- When adding admin API routes with static paths under `/admin/questions/` (e.g. `/export`, `/import`), register them **before** `{question_id}` routes, or use `{question_id:int}` path pattern to prevent routing conflicts
