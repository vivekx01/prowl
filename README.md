<div align="center">

# 🐾 The Prowl

### Stop scrolling job boards. Start hunting smarter.

**The Prowl** is a self-hosted job search engine that scrapes hundreds of company career portals, scores every listing against your resume using a two-stage LLM pipeline, and sends you the best-matched openings straight to Telegram — all from a single dashboard.

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
| 📣 | **Notify** | Get Telegram alerts for top-matched openings the moment they're found |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, Celery |
| Database | PostgreSQL (SQLite fallback for dev) |
| Task Queue | Celery + Redis |
| LLM | OpenRouter API (Gemini Flash, Gemini Flash Lite) |
| Scraping | HTTPX (async) |
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Charts | Apache ECharts |
| Auth | JWT (python-jose), bcrypt |
| Package Manager | uv (Python), npm (Node) |

---

## 🚀 Setup

There are two paths depending on what you want to do.

---

### Option A — Deploy on a server (recommended)

One script sets up Docker, generates secrets, and starts everything.

```bash
git clone <repo-url>
cd prowl
chmod +x setup.sh
./setup.sh
```

The script will:
- Install Docker if not already present
- Prompt for your OpenRouter API key and admin password
- Generate a secure `SECRET_KEY` and database password
- Write `.env.production` and start all containers

Once done, Prowl is live at `http://<your-server-ip>`. Log in with `admin@prowl.app` and the password you set.

---

### Option B — Local dev setup

#### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd prowl

# Python dependencies
uv sync

# Frontend dependencies
cd frontend && npm install && cd ..
```

#### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
OPENROUTER_API_KEY=your_key_here
ADMIN_PASSWORD=your_admin_password
```

#### 3. Start services

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

Open **http://localhost:5173** and log in with `admin@prowl.app` and your `ADMIN_PASSWORD`.

---

## ⚡ First Run

### 1. Log in
Use `admin@prowl.app` with the password you set during setup.

### 2. Set up your profile
Go to **Profile** and paste in your resume. This is the single most important step — Prowl scores every job listing against this profile, so the more detailed it is, the better your matches will be. Plain text or markdown works best.

### 3. Activate companies
Go to **Companies** and toggle on the companies you want to scrape. The list is seeded from `companies/companies.csv` — you can add more from the admin panel.

### 4. Set up a scraping schedule
Go to **Scrape** and configure a recurring schedule so Prowl automatically pulls fresh listings. You can also trigger a manual run immediately to get started.

### 5. Set up a scoring schedule
Go to **Users**, find your account, and configure a scoring schedule. This controls when Prowl runs your profile against newly scraped listings. A good pattern is to schedule scoring to run a few hours after scraping so there's always fresh content to process. You can also run scoring manually after any scrape.

### 6. Browse your matches
Once a scoring run completes, head to **Recommendations** to see your top-matched listings. Use the **Applications** tab to track anything you want to follow up on.

---

## 📁 Project Structure

```
prowl/
├── api/                    # FastAPI routes
│   ├── main.py             # App init, CORS, router mounting
│   ├── schemas.py          # Pydantic request/response models
│   ├── deps.py             # Auth dependencies
│   └── routers/            # auth, jobs, applications, score, scraper, admin...
│
├── db/
│   ├── database.py         # Engine, sessions, auto-migrations
│   └── models.py           # All SQLAlchemy models
│
├── scrapers/
│   ├── base.py             # BaseScraper ABC (extend to add new platforms)
│   ├── workday.py          # Workday implementation
│   ├── greenhouse.py       # Greenhouse implementation
│   ├── lever.py            # Lever implementation
│   └── ashby.py            # Ashby implementation
│
├── llm/
│   ├── filter.py           # Two-stage LLM filtering pipeline
│   ├── insights.py         # Analytics generation
│   └── resume_parser.py    # PDF/markdown resume parsing
│
├── frontend/               # React + TypeScript + TailwindCSS
│   └── src/
│       ├── pages/          # All page components
│       ├── components/     # Shared UI components
│       ├── context/        # Auth context
│       └── api/            # Axios client with auth interceptors
│
├── companies/
│   └── companies.csv       # Company → career portal seed data
│
├── runner.py               # Scrape orchestration
├── scorer.py               # Scoring orchestration
├── tasks.py                # Celery async task definitions
├── celery_app.py           # Celery configuration
├── config.py               # Env var loading
├── notify.py               # Telegram notification via Nexus
└── main.py                 # CLI entry point
```

---

## 🧠 LLM Scoring Pipeline

Jobs go through two stages to keep costs low:

**Stage 1 — Title filter**
Quickly eliminates jobs based on title alone — wrong seniority, irrelevant domain, etc.

**Stage 2 — Deep JD scoring**
Matches the full job description against your profile. Returns:
- `score` — 0 to 100
- `verdict` — `apply`, `maybe`, or `skip`
- `reason` — short explanation

Token costs are tracked per run and displayed in the UI (USD and INR).

---

## 📣 Telegram Notifications

Prowl does not send Telegram messages directly. Instead, after each scoring run it POSTs matched jobs to a webhook URL you provide. You need to build a small API that receives this payload and forwards it to Telegram using the [Telegram Bot API](https://core.telegram.org/bots/api).

**What Prowl sends** — a POST request to `NEXUS_NOTIFY_URL` with:

```
Header: X-Api-Key: <your secret key>
```

```json
{
  "event": "new_matches",
  "chat_id": "<user's telegram chat id>",
  "count": 3,
  "jobs": [
    { "title": "...", "company": "...", "score": 82, "verdict": "apply", "url": "..." }
  ],
  "link": "https://your-prowl-instance.com"
}
```

**What you need to build** — a simple HTTP endpoint (any language, any host) that:
1. Validates the `X-Api-Key` header against a secret you choose
2. Calls the Telegram Bot API to send a message to the `chat_id` in the payload

Once your webhook is running, set in `.env.production`:

```env
NEXUS_NOTIFY_URL=https://your-webhook.com/notify
NEXUS_API_KEY=the_secret_you_chose
PROWL_URL=https://your-prowl-instance.com
```

Then in Prowl's **Settings** page, enter your Telegram chat ID. Prowl will notify you whenever a scoring run finds `apply`-verdict jobs.

---

## 🔌 API Reference

### Auth
| Method | Endpoint | Description |
|---|---|---|
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
| PATCH | `/api/applications/{id}` | Update status |
| GET | `/api/applications` | List user applications |
| GET | `/api/applications/counts` | Status counts |

### Scraping (admin only)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/scraper/run` | Start scrape run |
| POST | `/api/scraper/stop/{run_id}` | Cancel active run |
| GET | `/api/runs` | Scrape run history |

### Scoring
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/score/run` | Start scoring run |
| GET | `/api/score/runs` | List scoring runs |
| GET | `/api/score/runs/{id}` | Run details + token usage |

Full API docs available at `http://localhost:8000/docs` when the backend is running.

---

## 🏢 Adding Companies

Companies are seeded from `companies/companies.csv` on first startup. Each row contains the company name, career portal URL, and scraper-specific config. Edit this file to add or remove companies before deploying — once the database is populated the CSV is not re-read.

The scraper layer is built on a `BaseScraper` abstraction — adding support for new career portal platforms is a matter of implementing the interface in `scrapers/`.

---

## 🤝 Contributing

PRs welcome. The project uses `uv` for Python dependency management — run `uv sync` after pulling to stay up to date.
