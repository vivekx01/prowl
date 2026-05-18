import asyncio
import re
from html.parser import HTMLParser

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from .base import BaseScraper, JobListing, is_india_or_remote

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

PAGE_SIZE = 100


async def resolve_config(url: str) -> tuple[dict, str | None]:
    """
    Resolve Oracle HCM company config from any careers/job URL (including custom domains).
    Returns (config_dict, warning_or_None).
    Raises ValueError if not a valid Oracle HCM portal.
    """
    m = re.search(r"/sites/([^/?#\s]+)", url)
    if not m:
        raise ValueError("Could not extract site number from URL — expected /sites/{name} in the path")
    site_number = m.group(1)

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=15,
        headers={"User-Agent": HEADERS["User-Agent"]},
        verify=False,
    ) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text
        except Exception as e:
            raise ValueError(f"Could not fetch URL: {e}")

    domain = None
    m2 = re.search(r"apiBaseUrl:\s*['\"]?(https://[^'\",:]+)", html)
    if m2:
        domain = m2.group(1).rstrip("/").replace("https://", "")
    else:
        # Oracle Cloud-hosted portals (*.fa.<region>.oraclecloud.com) serve the
        # REST API from the same host — the domain is right in the portal URL.
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        if re.search(r"\.fa\.[^.]+\.oraclecloud\.com$", host):
            domain = host

    if not domain:
        raise ValueError("Not a valid Oracle HCM portal — apiBaseUrl not found in page")

    # Verify API and fetch India location facet ID
    facets_url = f"https://{domain}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        try:
            r = await client.get(facets_url, params={
                "onlyData": "true",
                "finder": f"findReqs;siteNumber={site_number},limit=1",
            })
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            raise ValueError(f"Could not verify Oracle HCM API: {e}")

    items = data.get("items", [])
    india_facet_id = None
    warning = None

    if items:
        facets = items[0].get("locationsFacet", [])
        india = next((f["Id"] for f in facets if f["Name"] == "India"), None)
        if india:
            india_facet_id = india
        else:
            warning = (
                "No India jobs found on this portal — company added, "
                "scraper will fetch all locations and filter client-side"
            )
    else:
        warning = "Could not retrieve job facets — company added without India location filter"

    return {"domain": domain, "site_number": site_number, "india_facet_id": india_facet_id}, warning


class OracleHCMScraper(BaseScraper):
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers=HEADERS,
            timeout=config.REQUEST_TIMEOUT,
            follow_redirects=True,
            verify=False,
        )

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
        domain = company_row.get("domain", "").strip()
        site_number = company_row.get("site_number", "").strip()
        india_facet_id = company_row.get("india_facet_id")
        company = company_row["name"]

        if not domain or not site_number:
            raise RuntimeError(f"[oracle_hcm] {company}: missing 'domain' or 'site_number' in config")

        base_url = f"https://{domain}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        listings: list[JobListing] = []
        offset = 0

        while len(listings) < config.MAX_JOBS_PER_COMPANY:
            finder = f"findReqs;siteNumber={site_number},limit={PAGE_SIZE},offset={offset},sortBy=POSTING_DATES_DESC"
            if india_facet_id:
                finder += f",selectedLocationsFacet={india_facet_id}"

            try:
                data = await self._get(base_url, params={
                    "onlyData": "true",
                    "expand": "requisitionList",
                    "finder": finder,
                })
            except Exception as e:
                raise RuntimeError(
                    f"[oracle_hcm] {company} fetch error at offset {offset}: {e}"
                ) from e

            items = data.get("items", [])
            if not items:
                break

            search = items[0]
            req_list = search.get("requisitionList", [])
            total = search.get("TotalJobsCount", 0)

            if not req_list:
                break

            for job in req_list:
                job_id = str(job.get("Id", ""))
                location = job.get("PrimaryLocation", "")
                country = job.get("PrimaryLocationCountry", "")

                if not india_facet_id and not is_india_or_remote(location, country):
                    continue

                listings.append(JobListing(
                    company=company,
                    title=job.get("Title", ""),
                    job_id=job_id,
                    location=location,
                    posted_on=job.get("PostedDate", ""),
                    url=(
                        f"https://{domain}/hcmUI/CandidateExperience"
                        f"/en/sites/{site_number}/job/{job_id}"
                    ),
                    department=job.get("JobFamily", "") or job.get("JobFunction", ""),
                    raw={"_domain": domain, "_site": site_number, "_id": job_id},
                ))

            offset += PAGE_SIZE
            if offset >= total or len(req_list) < PAGE_SIZE:
                break

            await asyncio.sleep(config.REQUEST_DELAY)

        return listings

    async def fetch_detail(self, listing: JobListing) -> dict:
        domain = listing.raw.get("_domain", "")
        site = listing.raw.get("_site", "")
        job_id = listing.raw.get("_id", "")

        if not domain or not job_id:
            return {"description": "", "start_date": None}

        url = f"https://{domain}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
        try:
            data = await self._get(url, params={
                "onlyData": "true",
                "finder": f"ById;siteNumber={site},Id={job_id}",
            })
            items = data.get("items", [])
            if not items:
                return {"description": "", "start_date": None}
            detail = items[0]
            raw_html = detail.get("ExternalDescriptionStr") or ""
            start_date = detail.get("ExternalPostedStartDate", "")
            return {
                "description": _strip_html(raw_html),
                "start_date": start_date[:10] if start_date else None,
            }
        except Exception as e:
            print(f"  [oracle_hcm] detail fetch error for {listing.title}: {e}")
            return {"description": "", "start_date": None}


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
