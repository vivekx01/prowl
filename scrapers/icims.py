import re
import httpx
from html.parser import HTMLParser
from xml.etree import ElementTree as ET
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from .base import BaseScraper, JobListing, is_india_or_remote, is_clearly_foreign

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


class IcimsScraper(BaseScraper):
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers=HEADERS, timeout=config.REQUEST_TIMEOUT, follow_redirects=True
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_text(self, url: str) -> str:
        r = await self.client.get(url)
        r.raise_for_status()
        return r.text

    # ------------------------------------------------------------------
    # Sitemap parsing
    # ------------------------------------------------------------------

    async def _parse_sitemap(self, sitemap_url: str) -> list[tuple[str, str, str]]:
        """Returns list of (job_url, job_id, lastmod)."""
        xml_text = await self._get_text(sitemap_url)
        root = ET.fromstring(xml_text)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        jobs: list[tuple[str, str, str]] = []
        for url_el in root.findall("s:url", ns):
            loc_el = url_el.find("s:loc", ns)
            if loc_el is None:
                continue
            loc = loc_el.text or ""
            # Keep only individual job pages: /jobs/{id}/{title}/job
            if "/jobs/" not in loc or not loc.rstrip("/").endswith("/job"):
                continue
            # Extract numeric job ID from URL path
            m = re.search(r"/jobs/(\d+)/", loc)
            job_id = m.group(1) if m else ""
            if not job_id:
                continue
            lastmod_el = url_el.find("s:lastmod", ns)
            lastmod = lastmod_el.text if lastmod_el is not None else ""
            jobs.append((loc, job_id, lastmod))
        return jobs

    # ------------------------------------------------------------------
    # Detail fetch + JSON-LD extraction
    # ------------------------------------------------------------------

    async def _fetch_job(
        self, company: str, job_url: str, job_id: str, lastmod: str
    ) -> "JobListing | None":
        html = await self._get_text(job_url + "?in_iframe=1")

        import json as _json

        jsonld: dict = {}
        for raw in _JSONLD_RE.findall(html):
            try:
                data = _json.loads(raw.strip())
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    jsonld = data
                    break
            except Exception:
                continue

        if not jsonld:
            return None

        title = jsonld.get("title", "")

        # Location — jobLocation can be a list or a single dict
        job_locations = jsonld.get("jobLocation", [])
        if isinstance(job_locations, dict):
            job_locations = [job_locations]

        country = ""
        location_str = ""
        for loc in job_locations:
            addr = loc.get("address") or {}
            country = addr.get("addressCountry", "")
            city = addr.get("addressLocality", "")
            region = addr.get("addressRegion", "")
            location_str = ", ".join(filter(None, [city, region, country]))
            break  # use first location only

        # Remote detection: iCIMS sometimes sets jobLocationType
        job_loc_type = jsonld.get("jobLocationType", "")
        is_remote = job_loc_type == "TELECOMMUTE"

        if not is_remote and not is_india_or_remote(location_str, country) and is_clearly_foreign(location_str):
            return None

        description = _strip_html(jsonld.get("description", ""))
        department = jsonld.get("occupationalCategory", "")
        date_posted = jsonld.get("datePosted", "") or lastmod
        apply_url = jsonld.get("url", job_url)

        return JobListing(
            company=company,
            title=title,
            job_id=job_id,
            location=location_str,
            posted_on=date_posted,
            url=apply_url,
            department=department,
            raw={
                "_description": description,
                "_date": date_posted,
            },
        )

    # ------------------------------------------------------------------
    # BaseScraper interface
    # ------------------------------------------------------------------

    async def fetch_listings(self, company_row: dict) -> list[JobListing]:
        slug = company_row.get("slug", "").strip()
        # host override for non-standard patterns (e.g. "uscareers-docusign.icims.com")
        host = company_row.get("host", f"careers-{slug}.icims.com").strip()

        if not slug and not host:
            raise RuntimeError("[icims] company config missing 'slug' or 'host'")

        company = company_row["name"]
        sitemap_url = f"https://{host}/sitemap.xml"

        try:
            sitemap_jobs = await self._parse_sitemap(sitemap_url)
        except Exception as e:
            raise RuntimeError(f"[icims] {company} sitemap error: {e}") from e

        listings: list[JobListing] = []

        for job_url, job_id, lastmod in sitemap_jobs:
            if len(listings) >= config.MAX_JOBS_PER_COMPANY:
                break
            try:
                listing = await self._fetch_job(company, job_url, job_id, lastmod)
                if listing:
                    listings.append(listing)
            except Exception as e:
                print(f"  [icims] error on job {job_id}: {e}")
                continue

        return listings

    async def fetch_detail(self, listing: JobListing) -> dict:
        # Description was already fetched and cached during fetch_listings
        return {
            "description": listing.raw.get("_description", ""),
            "start_date": listing.raw.get("_date"),
        }


# ------------------------------------------------------------------
# HTML stripping
# ------------------------------------------------------------------

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
