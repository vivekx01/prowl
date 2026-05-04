from typing import Any

import httpx

from pounce import config
from pounce.auth.manager import auth_headers, get_server_url
from pounce.models import (
    AnswerMemoryRecord, JobRecord, LearnedFlowRecord,
    ListingRecord, ProfileData, RunResult,
)


def _base() -> str:
    return get_server_url().rstrip("/")


def _headers() -> dict:
    return auth_headers()


# ---------------------------------------------------------------------------
# Pull (server → client)
# ---------------------------------------------------------------------------

def fetch_jobs(min_score: float = 0.5) -> list[JobRecord]:
    with httpx.Client() as c:
        r = c.get(f"{_base()}/api/pounce/jobs",
                  params={"min_score": min_score},
                  headers=_headers(), timeout=15)
    r.raise_for_status()
    return [JobRecord(**j) for j in r.json()]


def fetch_profile() -> ProfileData:
    with httpx.Client() as c:
        r = c.get(f"{_base()}/api/pounce/profile", headers=_headers(), timeout=15)
    if r.status_code == 404:
        raise RuntimeError("No profile found on server — add one in The Prowl first")
    r.raise_for_status()
    return ProfileData(**r.json())


def fetch_memory() -> list[AnswerMemoryRecord]:
    with httpx.Client() as c:
        r = c.get(f"{_base()}/api/pounce/memory", headers=_headers(), timeout=15)
    r.raise_for_status()
    return [AnswerMemoryRecord(**m) for m in r.json()]


def fetch_flows() -> list[LearnedFlowRecord]:
    with httpx.Client() as c:
        r = c.get(f"{_base()}/api/pounce/flows", headers=_headers(), timeout=15)
    r.raise_for_status()
    return [LearnedFlowRecord(**f) for f in r.json()]


# ---------------------------------------------------------------------------
# Push (client → server)
# ---------------------------------------------------------------------------

def push_memory(entries: list[AnswerMemoryRecord]) -> int:
    if not entries:
        return 0
    payload = [e.model_dump(exclude={"id"}) for e in entries]
    with httpx.Client() as c:
        r = c.post(f"{_base()}/api/pounce/memory",
                   json=payload, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("upserted", 0)


def push_flows(flows: list[LearnedFlowRecord]) -> int:
    if not flows:
        return 0
    payload = [f.model_dump(exclude={"id"}) for f in flows]
    with httpx.Client() as c:
        r = c.post(f"{_base()}/api/pounce/flows",
                   json=payload, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("upserted", 0)


def fetch_listings(
    search: str | None = None,
    company: str | None = None,
    min_score: float = 0.0,
    limit: int = 50,
) -> list["ListingRecord"]:
    params: dict = {"limit": limit, "min_score": min_score}
    if search:
        params["search"] = search
    if company:
        params["company"] = company
    with httpx.Client() as c:
        r = c.get(f"{_base()}/api/pounce/listings",
                  params=params, headers=_headers(), timeout=15)
    r.raise_for_status()
    return [ListingRecord(**item) for item in r.json()]


def fetch_listing(listing_id: int) -> "ListingRecord":
    with httpx.Client() as c:
        r = c.get(f"{_base()}/api/pounce/listings/{listing_id}",
                  headers=_headers(), timeout=15)
    if r.status_code == 404:
        raise ValueError(f"Listing {listing_id} not found")
    r.raise_for_status()
    return ListingRecord(**r.json())


def mark_applied(application_id: int) -> None:
    with httpx.Client() as c:
        r = c.patch(
            f"{_base()}/api/applications/{application_id}",
            json={"status": "applied"},
            headers=_headers(),
            timeout=15,
        )
    r.raise_for_status()


def ensure_applied(listing_id: int) -> int:
    """Create or update an application record to 'applied'. Returns application_id."""
    with httpx.Client() as c:
        r = c.post(
            f"{_base()}/api/pounce/listings/{listing_id}/apply-record",
            headers=_headers(),
            timeout=15,
        )
    r.raise_for_status()
    return r.json()["application_id"]


def push_run(result: RunResult, listing_id: int | None) -> dict[str, Any]:
    payload = {
        "listing_id": listing_id,
        "status": result.status,
        "dry_run": result.dry_run,
        "agent_turns": result.agent_turns,
        "step_results": [s.model_dump() for s in result.step_results],
        "error_message": result.error_message,
    }
    with httpx.Client() as c:
        r = c.post(f"{_base()}/api/pounce/runs",
                   json=payload, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()
