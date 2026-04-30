from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


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
