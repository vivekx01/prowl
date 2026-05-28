import httpx
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from .base import BaseScraper, JobListing, is_india_or_remote

LEVER_BASE = "https://api.lever.co/v0/postings"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class LeverScraper(BaseScraper):
    def __init__(self):
        self.client = httpx.AsyncClient(headers=HEADERS, timeout=config.REQUEST_TIMEOUT, follow_redirects=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get(self, url: str) -> list:
        r = await self.client.get(url)
        r.raise_for_status()
        return r.json()

    async def fetch_listings(self, company_row: dict) -> list[JobListing]:
        slug = company_row.get("slug", "").strip()
        if not slug:
            raise RuntimeError("[lever] company config missing 'slug'")

        company = company_row["name"]
        url = f"{LEVER_BASE}/{slug}?mode=json"

        try:
            jobs = await self._get(url)
        except Exception as e:
            raise RuntimeError(f"[lever] {company} fetch error: {e}") from e

        if not isinstance(jobs, list):
            raise RuntimeError(f"[lever] {company}: unexpected response shape (expected list)")

        listings: list[JobListing] = []

        for job in jobs:
            if len(listings) >= config.MAX_JOBS_PER_COMPANY:
                break
            cats = job.get("categories") or {}
            location = cats.get("location", "")
            country = job.get("country", "")
            if not is_india_or_remote(location, country):
                continue

            created_ms = job.get("createdAt", 0)
            posted_iso = _ms_to_iso(created_ms)

            description = "\n\n".join(filter(None, [
                job.get("descriptionPlain", ""),
                job.get("descriptionBodyPlain", ""),
                job.get("additionalPlain", ""),
            ]))

            listings.append(
                JobListing(
                    company=company,
                    title=job.get("text", ""),
                    job_id=job.get("id", ""),
                    location=location,
                    posted_on=posted_iso,
                    url=job.get("hostedUrl", ""),
                    department=cats.get("department", ""),
                    raw={
                        "_description": description,
                        "_created_iso": posted_iso,
                        "id": job.get("id"),
                        "workplaceType": job.get("workplaceType", ""),
                        "commitment": cats.get("commitment", ""),
                        "team": cats.get("team", ""),
                    },
                )
            )

        return listings

    async def fetch_detail(self, listing: JobListing) -> dict:
        return {
            "description": listing.raw.get("_description", ""),
            "start_date": listing.raw.get("_created_iso"),
        }


def _ms_to_iso(ms: int) -> str:
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
