import io
import json
import unittest
from urllib.parse import parse_qs, urlparse

from placement_lens.sources.jobicy import fetch_jobicy_jobs, parse_jobicy_jobs


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._body


class ParseJobicyJobsTests(unittest.TestCase):
    def test_filters_normalizes_and_preserves_provenance(self):
        payload = {
            "jobs": [
                {
                    "id": 101,
                    "url": "https://jobicy.example/jobs/101",
                    "jobTitle": "Junior Data Analyst",
                    "companyName": "Acme",
                    "jobDescription": "<p>Use <strong>Python</strong> and SQL.</p>",
                    "jobGeo": "UK",
                    "jobLevel": "Entry-Level, Junior",
                    "pubDate": "2026-07-20T10:00:00+00:00",
                },
                {
                    "id": 102,
                    "url": "https://jobicy.example/jobs/102",
                    "jobTitle": "Machine Learning Engineer",
                    "companyName": "Beta",
                    "jobDescription": "Build models.",
                    "jobGeo": "Europe",
                    "jobLevel": "Any",
                    "pubDate": "2026-07-19T10:00:00+00:00",
                },
                {
                    "id": 103,
                    "url": "https://jobicy.example/jobs/103",
                    "jobTitle": "Data Scientist",
                    "companyName": "US Only",
                    "jobDescription": "Python.",
                    "jobGeo": "USA",
                    "jobLevel": "Senior",
                    "pubDate": "2026-07-18T10:00:00+00:00",
                },
                {
                    "id": 104,
                    "url": "https://jobicy.example/jobs/104",
                    "jobTitle": "Account Executive",
                    "companyName": "Not Data",
                    "jobDescription": "Manage sales accounts.",
                    "jobGeo": "Anywhere",
                    "jobLevel": "Any",
                    "pubDate": "2026-07-17T10:00:00+00:00",
                },
                {
                    "id": 105,
                    "url": "https://jobicy.example/jobs/105",
                    "jobTitle": "Data Analyst",
                    "companyName": "Old",
                    "jobDescription": "SQL.",
                    "jobGeo": "London, UK",
                    "jobLevel": "Entry Level",
                    "pubDate": "2025-12-31T10:00:00+00:00",
                },
            ]
        }

        jobs = parse_jobicy_jobs(payload, published_after="2026-01-01")

        self.assertEqual([job.job_id for job in jobs], ["jobicy:101", "jobicy:102"])
        self.assertEqual(jobs[0].description, "Use Python and SQL.")
        self.assertEqual(jobs[0].levels, ("Entry Level",))
        self.assertEqual(jobs[1].levels, ("Unspecified",))
        self.assertEqual(jobs[0].source, "Jobicy")
        self.assertEqual(jobs[0].source_url, "https://jobicy.example/jobs/101")
        self.assertEqual(jobs[0].published_at, "2026-07-20T10:00:00+00:00")


class FetchJobicyJobsTests(unittest.TestCase):
    def test_fetches_requested_count_and_tag(self):
        captured = {}
        payload = {
            "jobs": [
                {
                    "id": 201,
                    "url": "https://jobicy.example/jobs/201",
                    "jobTitle": "Data Scientist",
                    "companyName": "Acme",
                    "jobDescription": "Python.",
                    "jobGeo": "UK",
                    "jobLevel": "Entry Level",
                    "pubDate": "2026-07-20T10:00:00+00:00",
                }
            ]
        }

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["user_agent"] = request.headers["User-agent"]
            captured["timeout"] = timeout
            return FakeResponse(payload)

        jobs = fetch_jobicy_jobs(
            count=25,
            tag="data science",
            published_after="2026-01-01",
            opener=opener,
        )

        query = parse_qs(urlparse(captured["url"]).query)
        self.assertEqual(query["count"], ["25"])
        self.assertEqual(query["tag"], ["data science"])
        self.assertEqual(captured["timeout"], 30)
        self.assertIn("PlacementLensUK", captured["user_agent"])
        self.assertEqual([job.job_id for job in jobs], ["jobicy:201"])


if __name__ == "__main__":
    unittest.main()
