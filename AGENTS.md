# AGENTS.md

## Project Overview

MikanQuiz: Chinese character/font quiz system with a Vue 3 Web frontend and FastAPI backend.

## Miniprogram (Deprecated)

The `miniprogram/` and `cloudfunctions/quiz/` directories contain the original WeChat miniprogram client. **It is no longer maintained.** New features, bug fixes, and UI work should only target the Web frontend (`web/`). Do not add miniprogram compatibility when building new functionality.

## Directory Structure

- `web/frontend/` — Vue 3 + Vite Web frontend (TypeScript)
- `web/backend/` — FastAPI + SQLite backend (Python)
- `web/r2-uploader/` — Cloudflare R2 image upload adapter (Node.js)
- `miniprogram/` — ~~WeChat miniprogram~~ (deprecated, frozen)
- `cloudfunctions/quiz/` — ~~WeChat cloud functions~~ (deprecated, frozen)

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
cd web/backend && .venv/bin/python -m pytest tests -q

# Frontend API contract check + build
cd web/frontend && npm run test:api-contract && npm run build
```

## Architecture Notes

- **Database**: SQLite with WAL mode, single Uvicorn worker, Alembic migrations (never `create_all()`)
- **API**: All endpoints use `/api/v1` prefix, JSON, snake_case fields
- **Auth**: Web uses HttpOnly cookies; admin accounts managed via CLI only
- **Images**: Uploaded to Cloudflare R2 via server-side adapter; database stores public HTTPS URLs
- **Image upload flow**: On the question editor page, selected/pasted images are stored locally and shown as blob: URL previews. Upload to R2 happens together with question save, not immediately on selection. The save button shows a loading spinner and the form is disabled during save.

## Key Conventions

- Admin account management: `python -m app.admin_cli {add|list|password|disable|enable} USERNAME`
- Backend env vars: `QUIZ_DATABASE_URL`, `QUIZ_COOKIE_SECURE`, `QUIZ_ADMIN_SESSION_HOURS`
- R2 image upload env vars: `QUIZ_R2_ENDPOINT`, `QUIZ_R2_ACCESS_KEY_ID`, `QUIZ_R2_SECRET_ACCESS_KEY`, `QUIZ_R2_BUCKET`, `QUIZ_R2_PUBLIC_BASE_URL`
- Backend reads `.env` from `web/backend/.env` at startup (process env vars take precedence)
- Frontend uses Element Plus only for admin UI; public quiz UI is custom
- Design tokens defined in `DESIGN.md`; follow warm color palette (#FFF9F0 background, #A94F1F action)
- API contract: all snake_case fields, `/api/v1` prefix, errors as `{"error":{"code":"...","message":"..."}}`
- Question import/export: JSON format with `{version: 1, questions: [...]}`. Export includes `id`, `created_at`, `updated_at`; import ignores them (extra fields allowed). Image URLs are stored as-is from R2.

## Common Pitfalls

- Backend must have `.venv` created and activated before running
- Database migrations must run before starting backend (`alembic upgrade head`)
- Web frontend proxies `/api` to backend in dev mode
- When adding admin API routes with static paths under `/admin/questions/` (e.g. `/export`, `/import`), register them **before** `{question_id}` routes, or use `{question_id:int}` path pattern to prevent routing conflicts
