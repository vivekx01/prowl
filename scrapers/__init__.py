from scrapers.base import BaseScraper
from scrapers.workday import WorkdayScraper
from scrapers.greenhouse import GreenhouseScraper
from scrapers.lever import LeverScraper
from scrapers.oracle_hcm import OracleHCMScraper
from scrapers.smartrecruiters import SmartRecruitersScraper

# Map platform slug → scraper class.
# To add a new scraper: implement BaseScraper and register it here.
REGISTRY: dict[str, type[BaseScraper]] = {
    "workday": WorkdayScraper,
    "greenhouse": GreenhouseScraper,
    "lever": LeverScraper,
    "oracle_hcm": OracleHCMScraper,
    "smartrecruiters": SmartRecruitersScraper,
}


def get_scraper(platform: str) -> type[BaseScraper]:
    cls = REGISTRY.get(platform)
    if not cls:
        raise ValueError(
            f"No scraper registered for platform '{platform}'. "
            f"Available: {list(REGISTRY)}"
        )
    return cls
