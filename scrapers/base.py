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
        """Fetch all job listings for a company. Returns lightweight listing objects (no JD yet)."""

    @abstractmethod
    async def fetch_description(self, listing: JobListing) -> str:
        """Fetch full job description for a single listing."""
