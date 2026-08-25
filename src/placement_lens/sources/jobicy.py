"""Jobicy Remote Jobs API adapter with UK/Europe eligibility filtering."""

import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from placement_lens.matching import JobPosting
from placement_lens.sources.themuse import _html_to_text


API_URL = "https://jobicy.com/api/v2/remote-jobs"
USER_AGENT = "PlacementLensUK/0.1 (+portfolio research)"
ALLOWED_GEO_TERMS = (
    "united kingdom",
    "uk",
    "london",
    "europe",
    "emea",
    "anywhere",
    "worldwide",
)
ROLE_TERMS = (
    "data",
    "analytics",
    "machine learning",
    "ml engineer",
    "ai/ml",
    "artificial intelligence",
    "business intelligence",
)


def _normalize_level(raw_level: str) -> Tuple[str, ...]:
    normalized = raw_level.casefold()
    if "intern" in normalized:
        return ("Internship",)
    if any(term in normalized for term in ("entry", "junior", "graduate")):
        return ("Entry Level",)
    if any(
        term in normalized
        for term in ("senior", "principal", "lead", "director", "executive")
    ):
        return ("Senior Level",)
    if "mid" in normalized:
        return ("Mid Level",)
    if not normalized or normalized == "any":
        return ("Unspecified",)
    return (raw_level,)


def parse_jobicy_jobs(
    payload: Dict[str, Any],
    *,
    published_after: Optional[str] = None,
) -> List[JobPosting]:
    """Normalize eligible remote data roles while preserving source attribution."""
    jobs: List[JobPosting] = []
    for item in payload.get("jobs", []):
        published_at = item.get("pubDate", "")
        if published_after and (
            not published_at or published_at[:10] < published_after
        ):
            continue

        location = item.get("jobGeo", "")
        if not any(term in location.casefold() for term in ALLOWED_GEO_TERMS):
            continue

        title = item.get("jobTitle", "")
        raw_description = item.get("jobDescription", "")
        relevance_text = f"{title} {_html_to_text(raw_description)}".casefold()
        if not any(term in relevance_text for term in ROLE_TERMS):
            continue

        source_url = item.get("url", "")
        if not source_url:
            continue
        jobs.append(
            JobPosting(
                job_id=f"jobicy:{item.get('id', '')}",
                title=title,
                company=item.get("companyName", ""),
                description=_html_to_text(raw_description),
                location=location,
                levels=_normalize_level(item.get("jobLevel", "")),
                source="Jobicy",
                source_url=source_url,
                published_at=published_at,
            )
        )
    return jobs


def fetch_jobicy_jobs(
    *,
    count: int = 50,
    tag: str = "data science",
    published_after: Optional[str] = None,
    opener: Any = urlopen,
) -> List[JobPosting]:
    """Fetch and normalize jobs from Jobicy's documented public endpoint."""
    query = urlencode({"count": count, "tag": tag})
    request = Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": USER_AGENT},
    )
    with opener(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return parse_jobicy_jobs(payload, published_after=published_after)
