import httpx
from html.parser import HTMLParser
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from .base import BaseScraper, JobListing, is_india_or_remote

ASHBY_BASE = "https://api.ashbyhq.com/posting-api/job-board"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class AshbyScraper(BaseScraper):
    def __init__(self):
        self.client = httpx.AsyncClient(headers=HEADERS, timeout=config.REQUEST_TIMEOUT, follow_redirects=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get(self, url: str) -> dict:
        r = await self.client.get(url)
        r.raise_for_status()
        return r.json()

    async def fetch_listings(self, company_row: dict) -> list[JobListing]:
        slug = company_row.get("slug", "").strip()
        if not slug:
            raise RuntimeError("[ashby] company config missing 'slug'")

        company = company_row["name"]

        try:
            data = await self._get(f"{ASHBY_BASE}/{slug}")
        except Exception as e:
            raise RuntimeError(f"[ashby] {company} fetch error: {e}") from e

        jobs = data.get("jobs", [])
        listings: list[JobListing] = []

        for job in jobs:
            if len(listings) >= config.MAX_JOBS_PER_COMPANY:
                break

            # addressCountry is the full country name e.g. "India", not ISO code
            addr = (job.get("address") or {}).get("postalAddress") or {}
            country_name = addr.get("addressCountry", "")
            is_remote = job.get("isRemote", False)

            location = job.get("location", "") or ", ".join(filter(None, [
                addr.get("addressLocality", ""),
                addr.get("addressRegion", ""),
                country_name,
            ]))

            # is_india_or_remote checks country code (ISO-2) and location string;
            # Ashby gives full country name so rely on location string matching
            if not is_remote and not is_india_or_remote(location):
                continue

            description = _strip_html(job.get("descriptionHtml", ""))
            published = job.get("publishedAt", "")

            listings.append(
                JobListing(
                    company=company,
                    title=job.get("title", ""),
                    job_id=job.get("id", ""),
                    location=location,
                    posted_on=published,
                    url=job.get("jobUrl", ""),
                    department=job.get("department", ""),
                    raw={
                        "_description": description,
                        "_published": published,
                    },
                )
            )

        return listings

    async def fetch_detail(self, listing: JobListing) -> dict:
        # Description already fetched in fetch_listings — no extra HTTP request needed
        return {
            "description": listing.raw.get("_description", ""),
            "start_date": listing.raw.get("_published"),
        }


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str):
        self._parts.append(data)

    def get_text(self) -> str:
        return "\n".join(p for p in (s.strip() for s in self._parts) if p)


def _strip_html(html: str) -> str:
    if not html:
        return ""
    s = _HTMLStripper()
    s.feed(html)
    return s.get_text()
