from scrapers.base import BaseScraper
from scrapers.workday import WorkdayScraper

# Map platform slug → scraper class.
# To add a new scraper: implement BaseScraper and register it here.
REGISTRY: dict[str, type[BaseScraper]] = {
    "workday": WorkdayScraper,
}


def get_scraper(platform: str) -> type[BaseScraper]:
    cls = REGISTRY.get(platform)
    if not cls:
        raise ValueError(
            f"No scraper registered for platform '{platform}'. "
            f"Available: {list(REGISTRY)}"
        )
    return cls
