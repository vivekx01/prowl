import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST).replace(tzinfo=None)

load_dotenv()

BASE_DIR = Path(__file__).parent
COMPANIES_CSV = BASE_DIR / "companies" / "workday_companies.csv"
PROFILE_PATH = BASE_DIR / "profiles" / "my_profile.md"
RESULTS_DIR = BASE_DIR / "data" / "results"
DB_PATH = BASE_DIR / "data" / "jobs.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "prowl-secret-key-change-in-production")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

FILTER_MODEL    = os.getenv("FILTER_MODEL",    "google/gemini-2.5-flash-lite")
SCORE_MODEL     = os.getenv("SCORE_MODEL",     "google/gemini-2.5-flash")
INSIGHTS_MODEL  = os.getenv("INSIGHTS_MODEL",  "openai/gpt-4o-mini")

# Pricing per million tokens (USD) — override via env vars to match your actual models
FILTER_MODEL_PRICE_IN      = float(os.getenv("FILTER_MODEL_PRICE_IN",      "0.15"))
FILTER_MODEL_PRICE_OUT     = float(os.getenv("FILTER_MODEL_PRICE_OUT",     "0.60"))
SCORE_MODEL_PRICE_IN       = float(os.getenv("SCORE_MODEL_PRICE_IN",       "0.09"))
SCORE_MODEL_PRICE_OUT      = float(os.getenv("SCORE_MODEL_PRICE_OUT",      "0.45"))
SCORE_MODEL_CACHE_DISCOUNT = float(os.getenv("SCORE_MODEL_CACHE_DISCOUNT", "1.0"))

NEXUS_NOTIFY_URL = os.getenv("NEXUS_NOTIFY_URL", "")
NEXUS_API_KEY    = os.getenv("NEXUS_API_KEY", "")
PROWL_URL        = os.getenv("PROWL_URL", "")

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
MAX_JOBS_PER_COMPANY = int(os.getenv("MAX_JOBS_PER_COMPANY", "200"))

REQUEST_TIMEOUT = 30
LISTING_RETENTION_DAYS = int(os.getenv("LISTING_RETENTION_DAYS", "60"))

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
