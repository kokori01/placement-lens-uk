"""The Muse Public Jobs API normalization."""

from html.parser import HTMLParser
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from placement_lens.matching import JobPosting


BASE_URL = "https://www.themuse.com/api/public/jobs"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def _html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return parser.text()


def parse_jobs(
    payload: Dict[str, Any],
    *,
    required_location: str,
    required_category: str,
    published_after: Optional[str] = None,
) -> List[JobPosting]:
    """Normalize jobs and enforce exact location/category membership."""
    jobs: List[JobPosting] = []

    for item in payload.get("results", []):
        locations = tuple(
            location.get("name", "") for location in item.get("locations", [])
        )
        categories = {
            category.get("name", "") for category in item.get("categories", [])
        }
        if required_location not in locations or required_category not in categories:
            continue
        published_at = item.get("publication_date", "")
        if published_after and (
            not published_at or published_at[:10] < published_after
        ):
            continue

        jobs.append(
            JobPosting(
                job_id=f"themuse:{item['id']}",
                title=item.get("name", ""),
                company=item.get("company", {}).get("name", ""),
                description=_html_to_text(item.get("contents", "")),
                location=required_location,
                levels=tuple(
                    level.get("name", "") for level in item.get("levels", [])
                ),
                source="The Muse",
                source_url=item.get("refs", {}).get("landing_page", ""),
                published_at=published_at,
            )
        )

    return jobs


def fetch_jobs(
    *,
    location: str,
    category: str,
    pages: int,
    published_after: Optional[str] = None,
    opener: Any = urlopen,
    base_url: str = BASE_URL,
) -> List[JobPosting]:
    """Fetch and normalize a bounded number of The Muse result pages."""
    unique_jobs: Dict[str, JobPosting] = {}

    for page in range(pages):
        query = urlencode(
            {"page": page, "location": location, "category": category}
        )
        request = Request(
            f"{base_url}?{query}",
            headers={"User-Agent": "PlacementLensUK/0.1 (portfolio project)"},
        )
        with opener(request, timeout=30) as response:
            payload = json.load(response)

        for job in parse_jobs(
            payload,
            required_location=location,
            required_category=category,
            published_after=published_after,
        ):
            unique_jobs.setdefault(job.job_id, job)

    return list(unique_jobs.values())
