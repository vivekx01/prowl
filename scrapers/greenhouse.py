import httpx
from html.parser import HTMLParser
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from .base import BaseScraper, JobListing, is_clearly_foreign

GREENHOUSE_BASE = "https://boards-api.greenhouse.io/v1/boards"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class GreenhouseScraper(BaseScraper):
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
            raise RuntimeError("[greenhouse] company config missing 'slug'")

        company = company_row["name"]
        url = f"{GREENHOUSE_BASE}/{slug}/jobs?content=true"

        try:
            data = await self._get(url)
        except Exception as e:
            raise RuntimeError(f"[greenhouse] {company} fetch error: {e}") from e

        jobs = data.get("jobs", [])
        listings: list[JobListing] = []

        for job in jobs[: config.MAX_JOBS_PER_COMPANY]:
            job_id = str(job.get("id", ""))
            loc = job.get("location")
            location = loc.get("name", "") if isinstance(loc, dict) else ""
            if is_clearly_foreign(location):
                continue
            departments = job.get("departments") or []
            department = departments[0].get("name", "") if departments else ""
            updated_at = job.get("updated_at", "")

            listings.append(
                JobListing(
                    company=company,
                    title=job.get("title", ""),
                    job_id=job_id,
                    location=location,
                    posted_on=updated_at,
                    url=job.get("absolute_url", ""),
                    department=department,
                    raw={
                        "_slug": slug,
                        "_content": job.get("content", ""),
                        "id": job.get("id"),
                        "updated_at": updated_at,
                        "absolute_url": job.get("absolute_url", ""),
                    },
                )
            )

        return listings

    async def fetch_detail(self, listing: JobListing) -> dict:
        content = listing.raw.get("_content", "")
        updated_at = listing.raw.get("updated_at") or listing.posted_on

        if content:
            return {"description": _strip_html(content), "start_date": updated_at}

        # Fallback: hit the individual job endpoint (no content= in listing response)
        slug = listing.raw.get("_slug", "")
        if not slug or not listing.job_id:
            return {"description": "", "start_date": updated_at or None}

        url = f"{GREENHOUSE_BASE}/{slug}/jobs/{listing.job_id}"
        try:
            data = await self._get(url)
            return {
                "description": _strip_html(data.get("content", "")),
                "start_date": data.get("updated_at") or updated_at,
            }
        except Exception as e:
            print(f"  [greenhouse] detail fetch error for {listing.title}: {e}")
            return {"description": "", "start_date": updated_at or None}


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
