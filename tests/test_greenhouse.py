import json
import unittest
from urllib.parse import parse_qs, urlparse

from placement_lens.sources.greenhouse import (
    fetch_greenhouse_jobs,
    parse_greenhouse_jobs,
)


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._body


class ParseGreenhouseJobsTests(unittest.TestCase):
    def test_filters_uk_data_roles_and_preserves_update_provenance(self):
        payload = {
            "jobs": [
                {
                    "id": 101,
                    "title": "Data Analyst Intern",
                    "content": "<p>Use <strong>Python</strong> and SQL.</p>",
                    "location": {"name": "London, United Kingdom"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/101",
                    "updated_at": "2026-07-20T10:00:00-04:00",
                },
                {
                    "id": 102,
                    "title": "Machine Learning Engineer",
                    "content": "<p>Build production models.</p>",
                    "location": {"name": "Cardiff or Remote (UK)"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/102",
                    "updated_at": "2026-06-20T10:00:00-04:00",
                },
                {
                    "id": 103,
                    "title": "Data Scientist",
                    "content": "Python.",
                    "location": {"name": "New York, United States"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/103",
                    "updated_at": "2026-07-20T10:00:00-04:00",
                },
                {
                    "id": 104,
                    "title": "Account Executive",
                    "content": "Manage customer accounts.",
                    "location": {"name": "London"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/104",
                    "updated_at": "2026-07-20T10:00:00-04:00",
                },
                {
                    "id": 105,
                    "title": "Data Engineer",
                    "content": "Build pipelines.",
                    "location": {"name": "London"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/105",
                    "updated_at": "2026-08-01T10:00:00-04:00",
                },
                {
                    "id": 106,
                    "title": "Data Engineer",
                    "content": "Build pipelines.",
                    "location": {"name": "London"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/106",
                    "updated_at": "2025-12-31T10:00:00-04:00",
                },
            ]
        }

        jobs = parse_greenhouse_jobs(
            payload,
            board_token="acme",
            company="Acme",
            updated_after="2026-01-01",
            updated_before="2026-07-23",
        )

        self.assertEqual(
            [job.job_id for job in jobs],
            ["greenhouse:acme:101", "greenhouse:acme:102"],
        )
        self.assertEqual(jobs[0].description, "Use Python and SQL.")
        self.assertEqual(jobs[0].levels, ("Internship",))
        self.assertEqual(jobs[1].levels, ("Unspecified",))
        self.assertEqual(jobs[0].source, "Greenhouse")
        self.assertEqual(
            jobs[0].source_url,
            "https://job-boards.greenhouse.io/acme/jobs/101",
        )
        self.assertEqual(jobs[0].published_at, "2026-07-20T10:00:00-04:00")
        self.assertEqual(jobs[0].timestamp_kind, "updated")


class FetchGreenhouseJobsTests(unittest.TestCase):
    def test_fetches_each_registered_board_and_deduplicates_source_urls(self):
        requests = []
        shared = {
            "id": 201,
            "title": "Junior Data Analyst",
            "content": "Python.",
            "location": {"name": "London"},
            "absolute_url": "https://jobs.example/shared",
            "updated_at": "2026-07-20T10:00:00-04:00",
        }

        def opener(request, timeout):
            requests.append((request, timeout))
            return FakeResponse({"jobs": [shared]})

        jobs = fetch_greenhouse_jobs(
            boards={"alpha": "Alpha", "beta": "Beta"},
            updated_after="2026-01-01",
            updated_before="2026-07-23",
            opener=opener,
        )

        self.assertEqual(len(requests), 2)
        self.assertTrue(
            all(parse_qs(urlparse(request.full_url).query) == {"content": ["true"]}
                for request, _ in requests)
        )
        self.assertTrue(all(timeout == 30 for _, timeout in requests))
        self.assertTrue(
            all("PlacementLensUK" in request.headers["User-agent"]
                for request, _ in requests)
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source_url, "https://jobs.example/shared")


if __name__ == "__main__":
    unittest.main()
