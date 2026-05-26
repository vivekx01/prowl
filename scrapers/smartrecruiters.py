import httpx
from html.parser import HTMLParser
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from .base import BaseScraper, JobListing, is_india_or_remote

SR_BASE = "https://api.smartrecruiters.com/v1/companies"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class SmartRecruitersScraper(BaseScraper):
    def __init__(self):
        self.client = httpx.AsyncClient(headers=HEADERS, timeout=config.REQUEST_TIMEOUT, follow_redirects=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get(self, url: str, params: dict | None = None) -> dict:
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    async def fetch_listings(self, company_row: dict) -> list[JobListing]:
        slug = company_row.get("slug", "").strip()
        if not slug:
            raise RuntimeError("[smartrecruiters] company config missing 'slug'")

        company = company_row["name"]
        listings: list[JobListing] = []
        offset = 0
        limit = 100

        while len(listings) < config.MAX_JOBS_PER_COMPANY:
            try:
                data = await self._get(
                    f"{SR_BASE}/{slug}/postings",
                    params={"limit": limit, "offset": offset},
                )
            except Exception as e:
                raise RuntimeError(f"[smartrecruiters] {company} fetch error: {e}") from e

            postings = data.get("content", [])
            if not postings:
                break

            for job in postings:
                if len(listings) >= config.MAX_JOBS_PER_COMPANY:
                    break

                loc_obj = job.get("location") or {}
                # location.country is a plain ISO-2 string (e.g. "in"), not a nested object
                country_code = loc_obj.get("country", "")
                is_remote = loc_obj.get("remote", False)

                # fullLocation is pre-built by SR (e.g. "Bangalore, KA, India")
                location = loc_obj.get("fullLocation", "") or ", ".join(filter(None, [
                    loc_obj.get("city", ""),
                    loc_obj.get("region", ""),
                    country_code,
                ]))
                if is_remote and "remote" not in location.lower():
                    location = ("Remote, " + location).strip(", ")

                if not is_remote and not is_india_or_remote(location, country_code):
                    continue

                dept = (job.get("department") or {}).get("label", "")
                released = job.get("releasedDate", "")
                job_id = str(job.get("id", ""))
                # applyUrl is only in the detail endpoint; construct the public posting URL
                posting_url = f"https://jobs.smartrecruiters.com/{slug}/{job_id}"

                listings.append(
                    JobListing(
                        company=company,
                        title=job.get("name", ""),
                        job_id=job_id,
                        location=location,
                        posted_on=released,
                        url=posting_url,
                        department=dept,
                        raw={
                            "_slug": slug,
                            "_released": released,
                            "id": job_id,
                            "remote": is_remote,
                        },
                    )
                )

            total_found = data.get("totalFound", 0)
            offset += len(postings)
            if offset >= total_found:
                break

        return listings

    async def fetch_detail(self, listing: JobListing) -> dict:
        slug = listing.raw.get("_slug", "")
        job_id = listing.job_id
        released = listing.raw.get("_released") or listing.posted_on

        if not slug or not job_id:
            return {"description": "", "start_date": released or None}

        try:
            data = await self._get(f"{SR_BASE}/{slug}/postings/{job_id}")

            # Real apply URL is in the detail response
            apply_url = data.get("applyUrl", "") or data.get("postingUrl", "")
            if apply_url:
                listing.url = apply_url

            # Description lives in jobAd.sections — concatenate all section texts
            sections = (data.get("jobAd") or {}).get("sections") or {}
            ordered_keys = ["companyDescription", "jobDescription", "qualifications", "additionalInformation"]
            html_parts = [
                sections[k]["text"]
                for k in ordered_keys
                if k in sections and sections[k].get("text")
            ]
            description = _strip_html("\n".join(html_parts))

            return {
                "description": description,
                "start_date": data.get("releasedDate") or released,
            }
        except Exception as e:
            print(f"  [smartrecruiters] detail fetch error for {listing.title}: {e}")
            return {"description": "", "start_date": released or None}


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
