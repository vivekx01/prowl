from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

_INDIA_TERMS = frozenset([
    # Country
    "india",
    # Metros
    "bangalore", "bengaluru", "hyderabad", "mumbai", "delhi", "pune",
    "chennai", "kolkata", "gurgaon", "gurugram", "noida",
    # Tier-2 / commonly listed
    "ahmedabad", "kochi", "cochin", "trivandrum", "thiruvananthapuram",
    "coimbatore", "nagpur", "jaipur", "indore", "bhopal", "chandigarh",
    "lucknow", "bhubaneswar", "mangalore", "mysore", "mysuru",
    "visakhapatnam", "vizag", "thane", "navi mumbai", "new delhi",
    "surat", "vadodara", "patna", "kolkata",
    # Regions / abbreviations
    "ncr", "karnataka", "maharashtra", "telangana", "tamil nadu",
    # Remote
    "remote", "wfh", "work from home",
])

# Locations that unambiguously indicate a non-India country.
# Only used for is_clearly_foreign — kept conservative to avoid false negatives.
_FOREIGN_TERMS = frozenset([
    "united states", " usa", "u.s.a", "u.s.",
    "canada", "united kingdom", " uk,", "(uk)", "u.k.",
    "australia", "germany", "france", "singapore",
    "netherlands", "sweden", "norway", "denmark", "switzerland",
    "ireland", "spain", "italy", "poland", "austria",
    "brazil", "mexico", "argentina",
    "china", "japan", "south korea", "hong kong",
    "new york", "san francisco", "los angeles", "seattle", "boston",
    "chicago", "austin", "washington dc", "washington, d.c",
    "london", "toronto", "vancouver", "sydney", "melbourne",
    "berlin", "paris", "amsterdam", "dublin", "zurich",
    "singapore",
])


def is_india_or_remote(location: str, country: str = "") -> bool:
    """Return True if the job is based in India or is remote/WFH."""
    if country and country.upper() == "IN":
        return True
    loc = location.lower()
    return any(term in loc for term in _INDIA_TERMS)


def is_clearly_foreign(location: str) -> bool:
    """Return True only when the location is unambiguously outside India.

    Used as a conservative exclusion gate — when in doubt, returns False
    so the job is kept rather than silently dropped.
    """
    if not location:
        return False
    loc = location.lower()
    # Never exclude if any India indicator is present
    if any(term in loc for term in _INDIA_TERMS):
        return False
    return any(term in loc for term in _FOREIGN_TERMS)


@dataclass
class JobListing:
    company: str
    title: str
    job_id: str
    location: str
    posted_on: str
    url: str
    department: Optional[str] = None
    description: Optional[str] = None
    raw: dict = field(default_factory=dict)


class BaseScraper(ABC):
    @abstractmethod
    async def fetch_listings(self, company_row: dict) -> list[JobListing]:
        """Fetch all job listings for a company. Returns lightweight listing objects."""

    @abstractmethod
    async def fetch_detail(self, listing: JobListing) -> dict:
        """Fetch full job detail. Returns dict with 'description' (str) and 'start_date' (str | None)."""
