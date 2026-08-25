"""Selected-employer Greenhouse Job Board API adapter."""

import json
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import quote
from urllib.request import Request, urlopen

from placement_lens.matching import JobPosting
from placement_lens.sources.themuse import _html_to_text


API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
USER_AGENT = "PlacementLensUK/0.1 (+portfolio research)"

DEFAULT_BOARDS: Dict[str, str] = {
    "monzo": "Monzo",
    "wayve": "Wayve",
    "anthropic": "Anthropic",
    "physicsx": "PhysicsX",
    "grafanalabs": "Grafana Labs",
    "stripe": "Stripe",
    "gocardless": "GoCardless",
}

ROLE_PATTERN = re.compile(
    r"\b(?:data (?:scientist|analyst|engineer|architect|manager|specialist|director)"
    r"|analytics?|machine learning|ml engineer|ai engineer|business intelligence"
    r"|quantitative analyst|insights? analyst|applied scientist)\b",
    re.IGNORECASE,
)
UK_LOCATION_PATTERN = re.compile(
    r"\b(?:uk|united kingdom|england|scotland|wales|northern ireland|london|cardiff"
    r"|manchester|birmingham|bristol|cambridge|edinburgh|glasgow|leeds|belfast|oxford)\b",
    re.IGNORECASE,
)


def _normalize_level(title: str) -> Tuple[str, ...]:
    normalized = title.casefold()
    if any(term in normalized for term in ("intern", "placement", "apprentice")):
        return ("Internship",)
    if any(
        term in normalized
        for term in ("graduate", "junior", "entry level", "new grad", "early career")
    ):
        return ("Entry Level",)
    if any(
        term in normalized
        for term in (
            "senior", "staff", "principal", "lead", "manager", "director",
            "head", "vice president", "vp",
        )
    ):
        return ("Senior Level",)
    return ("Unspecified",)


def parse_greenhouse_jobs(
    payload: Dict[str, Any],
    *,
    board_token: str,
    company: str,
    updated_after: Optional[str] = None,
    updated_before: Optional[str] = None,
) -> List[JobPosting]:
    """Normalize current UK data roles from one public Greenhouse board."""
    jobs: List[JobPosting] = []
    for item in payload.get("jobs", []):
        title = item.get("title", "")
        location = (item.get("location") or {}).get("name", "")
        updated_at = item.get("updated_at", "")
        source_url = item.get("absolute_url", "")
        source_id = item.get("id")
        if not ROLE_PATTERN.search(title) or not UK_LOCATION_PATTERN.search(location):
            continue
        if updated_after and (not updated_at or updated_at[:10] < updated_after):
            continue
        if updated_before and (not updated_at or updated_at[:10] > updated_before):
            continue
        if source_id is None or not source_url:
            continue
        jobs.append(
            JobPosting(
                job_id=f"greenhouse:{board_token}:{source_id}",
                title=title,
                company=company,
                description=_html_to_text(item.get("content", "")),
                location=location,
                levels=_normalize_level(title),
                source="Greenhouse",
                source_url=source_url,
                published_at=updated_at,
                timestamp_kind="updated",
            )
        )
    return jobs


def fetch_greenhouse_jobs(
    *,
    boards: Mapping[str, str] = DEFAULT_BOARDS,
    updated_after: Optional[str] = None,
    updated_before: Optional[str] = None,
    opener: Any = urlopen,
) -> List[JobPosting]:
    """Fetch selected public boards with bounded, sequential requests."""
    jobs: List[JobPosting] = []
    seen_urls = set()
    for board_token, company in boards.items():
        request = Request(
            API_URL.format(board_token=quote(board_token, safe="")),
            headers={"User-Agent": USER_AGENT},
        )
        with opener(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        for job in parse_greenhouse_jobs(
            payload,
            board_token=board_token,
            company=company,
            updated_after=updated_after,
            updated_before=updated_before,
        ):
            if job.source_url in seen_urls:
                continue
            seen_urls.add(job.source_url)
            jobs.append(job)
    return jobs