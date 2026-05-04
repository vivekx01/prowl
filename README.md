<div align="center">

# 🐾 The Prowl

### Stop scrolling job boards. Start hunting smarter.

**The Prowl** is a self-hosted job search engine that scrapes hundreds of company career portals, scores every listing against your resume using a two-stage LLM pipeline, and lets an AI agent apply on your behalf — all from a single dashboard.

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![TailwindCSS](https://img.shields.io/badge/Tailwind-3-06B6D4?style=flat&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Celery](https://img.shields.io/badge/Celery-5-37814A?style=flat&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## ✨ What It Does

| | Feature | Description |
|---|---|---|
| 🕷️ | **Scrape** | Pulls fresh job listings from company career portals across multiple platforms |
| 🧠 | **Score** | Two-stage LLM pipeline scores each job against your resume and returns `apply`, `maybe`, or `skip` |
| 📋 | **Track** | Full application pipeline — saved → applied → interviewing → offer/rejected |
| 🐾 | **Pounce** | AI agent that reads, fills, and submits job application forms for you — learning as it goes |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, Celery |
| Database | PostgreSQL (SQLite fallback for dev) |
| Task Queue | Celery + Redis |
| LLM | OpenRouter API (Gemini Flash, Gemini Flash Lite) |
| Scraping | HTTPX (async), Playwright (browser automation) |
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Charts | Apache ECharts |
| Auth | JWT (python-jose), bcrypt |
| Package Manager | uv (Python), npm (Node) |

---

## 📋 Prerequisites

- Python 3.13+
- Node.js 18+
- PostgreSQL (or SQLite for local dev)
- Redis (required for Celery background tasks)
- [uv](https://docs.astral.sh/uv/) — fast Python package manager
- An [OpenRouter](https://openrouter.ai/) API key

---

## 🚀 Setup

### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd "Job Scrapper"

# Python dependencies
uv sync

# Frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENROUTER_API_KEY=your_key_here

# PostgreSQL (or remove for SQLite fallback)
DATABASE_URL=postgresql://user:password@localhost:5432/jobscrapper

# LLM models (via OpenRouter)
FILTER_MODEL=google/gemini-2.5-flash-lite   # Stage 1 — cheap & fast
SCORE_MODEL=google/gemini-2.5-flash          # Stage 2 — quality scoring

# Scraper behavior
REQUEST_DELAY=1.5          # Seconds between requests per company
MAX_JOBS_PER_COMPANY=200   # Cap listings per scrape

# Token pricing per million (USD) — used for per-run cost display
FILTER_MODEL_PRICE_IN=0.10
FILTER_MODEL_PRICE_OUT=0.40
SCORE_MODEL_PRICE_IN=0.15
SCORE_MODEL_PRICE_OUT=0.60
SCORE_MODEL_CACHE_DISCOUNT=0.25
```

### 3. Start services

Open four terminals:

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: FastAPI backend
uv run fastapi dev api/main.py
# Runs on http://localhost:8000

# Terminal 3: Celery worker (background tasks)
celery -A celery_app worker --loglevel=info

# Terminal 4: React frontend
cd frontend && npm run dev
# Runs on http://localhost:5173
```

Open **http://localhost:5173** in your browser.

---

## ⚡ First Run

1. **Register** — The first registered user is automatically made admin
2. **Upload your profile** — Go to Profile and paste or upload your resume (markdown or PDF)
3. **Activate companies** — Go to Companies and toggle on the companies you want to scrape
4. **Scrape** — Go to Scrape (admin), select companies, and start a run
5. **Score** — Trigger a scoring run once scraping completes; this runs your profile against all fresh listings
6. **Browse jobs** — Head to the Jobs page and filter by `apply`, `maybe`, or `skip`

---

## 📁 Project Structure

```
Job Scrapper/
├── api/                    # FastAPI routes
│   ├── main.py             # App init, CORS, router mounting
│   ├── schemas.py          # Pydantic request/response models
│   ├── deps.py             # Auth dependencies
│   └── routers/            # auth, jobs, applications, score, scraper, pounce, admin...
│
├── db/
│   ├── database.py         # Engine, sessions, auto-migrations
│   └── models.py           # All SQLAlchemy models
│
├── scrapers/
│   ├── base.py             # BaseScraper ABC (extend to add new platforms)
│   └── workday.py          # Workday implementation
│
├── llm/
│   ├── filter.py           # Two-stage LLM filtering pipeline
│   ├── insights.py         # Analytics generation
│   └── resume_parser.py    # PDF/markdown resume parsing
│
├── pounce/                 # Auto-application bot
│   ├── agent/              # Claude-based Playwright agent
│   ├── core/               # Runner, session, human-in-the-loop
│   ├── memory/             # Answer caching + learned flows
│   └── auth/               # Workday credential management
│
├── frontend/               # React + TypeScript + TailwindCSS
│   └── src/
│       ├── pages/          # All page components
│       ├── components/     # Shared UI components
│       ├── context/        # Auth context
│       └── api/            # Axios client with auth interceptors
│
├── runner.py               # Scrape orchestration
├── scorer.py               # Scoring orchestration
├── tasks.py                # Celery async task definitions
├── celery_app.py           # Celery configuration
├── config.py               # Env var loading
└── main.py                 # CLI entry point
```

---

## 🧠 LLM Scoring Pipeline

Jobs go through two stages to keep costs low:

**Stage 1 — Title filter** (Gemini Flash Lite, ~$0.0001/job)
Quickly eliminates jobs based on title alone — wrong seniority, irrelevant domain, etc.

**Stage 2 — Deep JD scoring** (Gemini Flash, ~$0.001/job)
Matches the full job description against your profile. Returns:
- `score` — 0 to 100
- `verdict` — `apply`, `maybe`, or `skip`
- `reason` — short explanation

Token costs are tracked per run and displayed in the UI (USD and INR).

---

## 🔌 API Reference

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/auth/me` | Current user info |

### Jobs
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/jobs` | List jobs (`?verdict=apply&score_min=70`) |
| GET | `/api/jobs/{id}` | Job detail |

### Applications
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/applications` | Save/apply to job |
| PUT | `/api/applications/{id}` | Update status |
| GET | `/api/applications` | List user applications |

### Scraping (admin only)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/scraper/run` | Start scrape run |
| POST | `/api/scraper/stop/{run_id}` | Cancel active run |
| POST | `/api/scraper/resume/{run_id}` | Resume failed run |
| GET | `/api/runs` | Scrape run history |

### Scoring
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/score/run` | Start scoring run |
| GET | `/api/score/runs` | List scoring runs |
| GET | `/api/score/runs/{id}` | Run details + token usage |

### Pounce
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/pounce/run` | Start auto-application |
| POST | `/api/pounce/run/{id}/cancel` | Cancel run |
| GET | `/api/pounce/answers` | Cached form answers |
| GET | `/api/pounce/flows` | Learned application flows |

Full API docs available at `http://localhost:8000/docs` when the backend is running.

---

## 🐾 Pounce — Auto Application Bot

Pounce is an AI agent that uses Playwright to navigate career portals and fill out application forms. It:

- Uses Claude (via OpenRouter) to reason about form fields and choose the right answers
- Caches answers by normalized question text — gets faster with every application
- Stores learned step-by-step flows per company for one-click replay
- Supports dry-run mode to preview before submitting anything real
- Includes human-in-the-loop checkpoints for sensitive or ambiguous fields

> Pounce is experimental. Always review before submitting real applications.

---

## 💻 CLI Usage

For running scrapes without the web UI:

```bash
uv run python main.py
```

This launches an interactive CLI (via questionary) to select companies and trigger scrape/score runs directly.

---

## 🏢 Adding Companies

Companies are seeded from `companies/workday_companies.csv`. Each row contains the company name, career portal URL, and any scraper-specific config. To add a new company, add a row to the CSV and re-seed via the admin panel or CLI.

The scraper layer is built on a `BaseScraper` abstraction — adding support for new career portal platforms (Greenhouse, Lever, Ashby, etc.) is a matter of implementing the interface in `scrapers/`.

---

## 🤝 Contributing

PRs welcome. The project uses `uv` for Python dependency management — run `uv sync` after pulling to stay up to date.
