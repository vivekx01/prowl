# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**Prowl** is a self-hosted job search automation platform. It scrapes company career portals, scores job listings against the user's resume using a two-stage LLM pipeline, tracks applications, and can auto-fill/submit applications via an AI agent ("Pounce").

## Commands

### Backend (Python)
```bash
uv sync                                          # Install dependencies
uv run fastapi dev api/main.py                   # Start API server (localhost:8000, hot reload)
uv run python main.py                            # Interactive CLI menu (scrape/score)
celery -A celery_app worker --loglevel=info      # Start Celery worker
celery -A celery_app beat --loglevel=info        # Start Celery Beat scheduler
```

### Frontend
```bash
cd frontend && npm install
npm run dev          # Vite dev server (localhost:5173, proxies /api to localhost:8000)
npm run build        # TypeScript + TailwindCSS production build
```

### Docker (Production)
```bash
docker compose --env-file .env.production up -d --build
docker compose logs -f <service>   # services: postgres, redis, api, worker, nginx
docker compose restart <service>
```

## Architecture

```
Frontend (React/Vite) → FastAPI (api/) → PostgreSQL + Redis
                              ↓
                        Celery Worker (tasks.py)
                         ↙           ↘
               Scrapers (scrapers/)  LLM Pipeline (llm/)
                                          ↓
                                  Pounce Agent (pounce/)
```

**Request flow:** Frontend sends JWT-authenticated requests → FastAPI routes in `api/routers/` → triggers Celery tasks for long-running work → results stored in PostgreSQL → frontend polls or reloads.

**Auth:** First registered user becomes admin. JWT tokens managed via `AuthContext` on frontend, validated in `api/deps.py` on backend.

**Database:** SQLAlchemy ORM in `db/models.py`. No migration framework — tables are created/altered via `init_db()` on startup (`db/database.py`). Add new columns carefully since SQLite (dev) and PostgreSQL (prod) handle `ALTER TABLE` differently.

## Key Modules

### `api/`
FastAPI app (`main.py`), Pydantic schemas (`schemas.py`), 12 routers in `api/routers/`. CORS and lifespan hooks (including `init_db()`) are in `main.py`.

### `scrapers/`
Four scrapers inheriting from `BaseScraper` (`base.py`): Workday, Greenhouse, Lever, Oracle HCM. Each implements `get_listings()`. Registered in `__init__.py`. To add a new portal, subclass `BaseScraper` and register it.

### `llm/`
Two-stage scoring pipeline in `filter.py`:
1. **Stage 1 (fast filter):** Gemini Flash Lite — title-only relevance check
2. **Stage 2 (deep score):** Gemini Flash — full JD vs. resume scoring → 0-100 + verdict (apply/maybe/skip)

Uses OpenRouter API via LangChain. Token costs are tracked per run.

### `pounce/`
Claude-based browser agent (`pounce/agent/browser_agent.py`) that auto-fills job applications using Playwright. Maintains a `flow_store` (learned application flows per company) and `answer_store` (cached answers to form questions). Human review checkpoints are in `human_loop.py`. Scheduled via APScheduler daemon.

### `tasks.py` + `celery_app.py`
All long-running work (scraping, scoring) runs as Celery tasks. Beat schedule: `check_schedule_task` every minute, `cleanup_old_listings` daily at 2 AM IST.

### `runner.py` / `scorer.py`
Orchestration logic called by Celery tasks and the CLI. `runner.py` handles company iteration and scraper dispatch; `scorer.py` manages LLM pipeline execution and cost tracking.

### `notify.py`
Sends high-scoring job matches to an external Nexus service (`NEXUS_NOTIFY_URL`), which relays them via Telegram bot.

## Environment

Copy `.env.example` to `.env` (dev) or `.env.production` (Docker). Key variables:
- `DATABASE_URL` — defaults to SQLite (`data/jobs.db`) if unset
- `OPENROUTER_API_KEY` — required for scraping and scoring
- `FILTER_MODEL` / `SCORE_MODEL` — OpenRouter model IDs for two-stage pipeline
- `NEXUS_NOTIFY_URL` / `NEXUS_API_KEY` — optional, for Telegram notifications
- `SECRET_KEY` — JWT signing secret (required in production)
- `ALLOWED_ORIGINS` — CORS origins (default: `http://localhost:5173`)

## Companies Data

`companies/workday_companies.csv` seeds company → career portal mappings on first startup. To add companies, edit this CSV or use the Admin page in the UI.

## Timezone

All timestamps use IST (Asia/Kolkata). Celery Beat schedules are defined in IST. Frontend displays times in IST via `ISTTimePicker` component.

## CI/CD

Push to `main` → GitHub Actions (`.github/workflows/deploy.yml`) → SSH into server → `docker compose up -d --build`. Requires secrets: `SSH_HOST`, `SSH_USER`, `SSH_KEY`.
