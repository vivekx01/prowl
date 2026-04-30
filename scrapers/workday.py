import asyncio
import json
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from .base import BaseScraper, JobListing

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class WorkdayScraper(BaseScraper):
    def __init__(self):
        self.client = httpx.AsyncClient(headers=HEADERS, timeout=config.REQUEST_TIMEOUT, follow_redirects=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _post(self, url: str, payload: dict) -> dict:
        r = await self.client.post(url, json=payload)
        r.raise_for_status()
        return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get(self, url: str, referer: str = "") -> dict:
        headers = {"Referer": referer} if referer else {}
        r = await self.client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()

    async def fetch_listings(self, company_row: dict) -> list[JobListing]:
        """
        CSV columns used:
        - Company Name
        - Job listing fetch  (POST endpoint ending in /jobs)
        - Payload            (JSON string with appliedFacets etc.)
        - Base careers page  (used to build public apply URL)
        """
        company = company_row["name"]
        endpoint = company_row["listing_endpoint"].strip().rstrip("/")
        base_careers_url = company_row.get("base_careers_url", "").strip().rstrip("/")
        jd_base = company_row.get("jd_base", "").strip().rstrip("/")
        base_payload: dict = json.loads(company_row.get("payload") or "{}")

        listings: list[JobListing] = []
        offset = 0
        limit = 20

        while len(listings) < config.MAX_JOBS_PER_COMPANY:
            payload = {**base_payload, "limit": limit, "offset": offset}
            try:
                data = await self._post(endpoint, payload)
            except Exception as e:
                print(f"  [workday] {company} fetch error at offset {offset}: {e}")
                break

            postings = data.get("jobPostings", [])
            if not postings:
                break

            for p in postings:
                external_path = p.get("externalPath", "")
                # Public apply URL: base_careers_page + externalPath
                public_url = (base_careers_url + external_path) if base_careers_url else (
                    _extract_base_domain(endpoint) + "/en-US" + external_path
                )
                # Stash the JD base so fetch_description can build the detail API URL
                p["_jd_base"] = jd_base

                listings.append(JobListing(
                    company=company,
                    title=p.get("title", ""),
                    job_id=p.get("jobReqId", "") or external_path.split("/")[-1],
                    location=p.get("locationsText", ""),
                    posted_on=p.get("postedOn", ""),
                    url=public_url,
                    department=p.get("jobFamilyGroup", ""),
                    raw=p,
                ))

            offset += limit
            if len(postings) < limit:
                break

            await asyncio.sleep(config.REQUEST_DELAY)

        return listings

    async def fetch_detail(self, listing: JobListing) -> dict:
        """Fetch full job detail via Workday's CXS API.
        Returns description text and startDate (ISO string or None).
        """
        external_path = listing.raw.get("externalPath", "")
        jd_base = listing.raw.get("_jd_base", "")
        if not external_path or not jd_base:
            return {"description": "", "start_date": None}

        detail_api = jd_base + external_path
        try:
            data = await self._get(detail_api, referer=listing.url)
            jd = data.get("jobPostingInfo", {})
            return {
                "description": _extract_jd_text(jd),
                "start_date": jd.get("startDate"),
            }
        except Exception as e:
            print(f"  [workday] detail fetch error for {listing.title}: {e}")
            return {"description": "", "start_date": None}


def _extract_base_domain(endpoint: str) -> str:
    """https://acme.wd5.myworkdayjobs.com/wday/cxs/... -> https://acme.wd5.myworkdayjobs.com"""
    from urllib.parse import urlparse
    p = urlparse(endpoint)
    return f"{p.scheme}://{p.netloc}"


def _extract_jd_text(jd: dict) -> str:
    """Pull readable text from Workday's jobPostingInfo blob."""
    parts = []
    for key in ("jobDescription", "additionalJobDescription"):
        val = jd.get(key, {})
        if isinstance(val, dict):
            parts.append(val.get("content", ""))
        elif isinstance(val, str):
            parts.append(val)
    return "\n\n".join(filter(None, parts))
