import io
import json
import unittest
from urllib.parse import parse_qs, urlparse

from placement_lens.sources.themuse import fetch_jobs, parse_jobs


class ParseTheMuseJobsTests(unittest.TestCase):
    def test_keeps_exact_london_data_roles_and_preserves_provenance(self):
        payload = {
            "results": [
                {
                    "id": 123,
                    "name": "Junior Data Scientist",
                    "company": {"name": "Acme Analytics"},
                    "contents": "<p>Build models with Python &amp; SQL.</p>",
                    "locations": [{"name": "London, United Kingdom"}],
                    "categories": [{"name": "Data and Analytics"}],
                    "levels": [{"name": "Entry Level"}],
                    "publication_date": "2026-07-22T09:30:00Z",
                    "refs": {"landing_page": "https://example.test/jobs/123"},
                },
                {
                    "id": 456,
                    "name": "Remote Data Scientist",
                    "company": {"name": "Remote Co"},
                    "contents": "<p>Python</p>",
                    "locations": [{"name": "Flexible / Remote"}],
                    "categories": [{"name": "Data and Analytics"}],
                    "levels": [{"name": "Mid Level"}],
                    "publication_date": "2026-07-21T09:30:00Z",
                    "refs": {"landing_page": "https://example.test/jobs/456"},
                },
            ]
        }

        jobs = parse_jobs(
            payload,
            required_location="London, United Kingdom",
            required_category="Data and Analytics",
        )

        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.job_id, "themuse:123")
        self.assertEqual(job.title, "Junior Data Scientist")
        self.assertEqual(job.company, "Acme Analytics")
        self.assertEqual(job.description, "Build models with Python & SQL.")
        self.assertEqual(job.location, "London, United Kingdom")
        self.assertEqual(job.levels, ("Entry Level",))
        self.assertEqual(job.source, "The Muse")
        self.assertEqual(job.source_url, "https://example.test/jobs/123")
        self.assertEqual(job.published_at, "2026-07-22T09:30:00Z")

    def test_excludes_jobs_older_than_published_after(self):
        def item(job_id, published_at):
            return {
                "id": job_id,
                "name": "Data Analyst",
                "company": {"name": "Acme"},
                "contents": "<p>SQL</p>",
                "locations": [{"name": "London, United Kingdom"}],
                "categories": [{"name": "Data and Analytics"}],
                "levels": [{"name": "Internship"}],
                "publication_date": published_at,
                "refs": {"landing_page": f"https://example.test/jobs/{job_id}"},
            }

        jobs = parse_jobs(
            {"results": [item(1, "2025-03-01T00:00:00Z"), item(2, "2026-04-01T00:00:00Z")]},
            required_location="London, United Kingdom",
            required_category="Data and Analytics",
            published_after="2026-01-01",
        )

        self.assertEqual([job.job_id for job in jobs], ["themuse:2"])


class FetchTheMuseJobsTests(unittest.TestCase):
    def test_fetches_requested_pages_and_deduplicates_jobs(self):
        seen_pages = []
        payload = {
            "results": [
                {
                    "id": 123,
                    "name": "Junior Data Scientist",
                    "company": {"name": "Acme Analytics"},
                    "contents": "<p>Python and SQL</p>",
                    "locations": [{"name": "London, United Kingdom"}],
                    "categories": [{"name": "Data and Analytics"}],
                    "levels": [{"name": "Entry Level"}],
                    "publication_date": "2026-07-22T09:30:00Z",
                    "refs": {"landing_page": "https://example.test/jobs/123"},
                }
            ]
        }

        def opener(request, timeout):
            self.assertEqual(timeout, 30)
            self.assertIn("PlacementLensUK", request.get_header("User-agent"))
            query = parse_qs(urlparse(request.full_url).query)
            seen_pages.append(int(query["page"][0]))
            return io.BytesIO(json.dumps(payload).encode("utf-8"))

        jobs = fetch_jobs(
            location="London, United Kingdom",
            category="Data and Analytics",
            pages=2,
            opener=opener,
        )

        self.assertEqual(seen_pages, [0, 1])
        self.assertEqual([job.job_id for job in jobs], ["themuse:123"])


if __name__ == "__main__":
    unittest.main()
