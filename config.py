import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
COMPANIES_CSV = BASE_DIR / "companies" / "workday_companies.csv"
PROFILE_PATH = BASE_DIR / "profiles" / "my_profile.md"
RESULTS_DIR = BASE_DIR / "data" / "results"
DB_PATH = BASE_DIR / "data" / "jobs.db"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

FILTER_MODEL = os.getenv("FILTER_MODEL", "google/gemini-2.5-flash-lite")
SCORE_MODEL = os.getenv("SCORE_MODEL", "google/gemini-2.5-flash-lite")

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
MAX_JOBS_PER_COMPANY = int(os.getenv("MAX_JOBS_PER_COMPANY", "200"))

REQUEST_TIMEOUT = 30

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
