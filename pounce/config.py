import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)
# Also check pounce subdir in case user runs from project root
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

# Server
API_BASE_URL: str = os.getenv("POUNCE_API_BASE_URL", "http://localhost:8000")

# LLM
POUNCE_MODEL: str = os.getenv("POUNCE_MODEL", "google/gemini-2.5-flash")
POUNCE_VISION_MODEL: str = os.getenv("POUNCE_VISION_MODEL", "google/gemini-2.5-pro")
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

# Resume
POUNCE_RESUME_PATH: str = os.getenv("POUNCE_RESUME_PATH", "")

# Local profile override — if set, used instead of the server profile
POUNCE_PROFILE_PATH: str = os.getenv("POUNCE_PROFILE_PATH", "")

# Portal credentials (used for sign-in on job portals)
POUNCE_PORTAL_EMAIL: str = os.getenv("POUNCE_PORTAL_EMAIL", "")
POUNCE_PORTAL_PASSWORD: str = os.getenv("POUNCE_PORTAL_PASSWORD", "")

# Browser
POUNCE_HEADLESS: bool = os.getenv("POUNCE_HEADLESS", "true").lower() == "true"
POUNCE_SLOW_MO: int = int(os.getenv("POUNCE_SLOW_MO", "0"))
POUNCE_STEP_TIMEOUT: int = int(os.getenv("POUNCE_STEP_TIMEOUT", "30000"))
POUNCE_MAX_AGENT_TURNS: int = int(os.getenv("POUNCE_MAX_AGENT_TURNS", "50"))

# Local state
POUNCE_DIR: Path = Path.home() / ".pounce"
POUNCE_DIR.mkdir(parents=True, exist_ok=True)

CREDENTIALS_FILE: Path = POUNCE_DIR / "credentials.json"
CONFIG_FILE: Path = POUNCE_DIR / "config.json"
SCHEDULER_DB: Path = POUNCE_DIR / "scheduler.db"
SCREENSHOTS_DIR: Path = POUNCE_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
