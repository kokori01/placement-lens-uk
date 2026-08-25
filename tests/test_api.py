import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from placement_lens.api import create_app
from placement_lens.storage import (
    initialize_database,
    load_candidate,
    load_jobs,
    load_ranking_run,
)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        with sqlite3.connect(self.database_path) as connection:
            initialize_database(connection)
            load_jobs(
                connection,
                [
                    {
                        "id": "a", "title": "Data Analyst", "company": "Acme",
                        "description": "Python and SQL", "location": "London",
                        "levels": ["Entry Level"], "source": "The Muse",
                        "source_url": "https://jobs.example/a",
                        "published_at": "2026-07-20T10:00:00Z",
                    },
                    {
                        "id": "b", "title": "ML Intern", "company": "Beta",
                        "description": "Python and AWS", "location": "UK",
                        "levels": ["Internship"], "source": "Jobicy",
                        "source_url": "https://jobs.example/b",
                        "published_at": "2026-07-19T10:00:00Z",
                    },
                ],
            )
            load_candidate(
                connection,
                {
                    "candidate_id": "candidate-local",
                    "target_location": "London",
                    "profile_text": "Python data analysis",
                    "skills": ["Python"],
                },
            )
            load_ranking_run(
                connection,
                candidate_id="candidate-local",
                model_version="hybrid-v1",
                payload={
                    "ranked_jobs": [
                        {
                            "job_id": "a", "score": 62.5,
                            "skill_coverage": 50.0, "skill_confidence": 66.7,
                            "skill_score": 33.4, "title_score": 100.0,
                            "text_score": 20.0, "level_score": 100.0,
                            "matched_skills": ["python"],
                            "missing_skills": ["sql"],
                        },
                        {
                            "job_id": "b", "score": 40.0,
                            "skill_coverage": 57.1, "skill_confidence": 66.7,
                            "skill_score": 38.1, "title_score": 0.0,
                            "text_score": 6.0, "level_score": 100.0,
                            "matched_skills": ["python"],
                            "missing_skills": ["aws"],
                        },
                    ]
                },
            )
        self.client = TestClient(create_app(self.database_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_health_summary_and_filtered_jobs_endpoints(self):
        health = self.client.get("/api/health")
        summary = self.client.get("/api/summary")
        jobs = self.client.get(
            "/api/jobs",
            params={"source": "Jobicy", "level": "Internship", "limit": 10},
        )

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["total_jobs"], 2)
        self.assertEqual(jobs.status_code, 200)
        self.assertEqual(jobs.json()["count"], 1)
        self.assertEqual(jobs.json()["jobs"][0]["job_id"], "b")

    def test_skills_gaps_and_dashboard_are_served(self):
        skills = self.client.get("/api/skills", params={"limit": 3})
        gaps = self.client.get("/api/gaps", params={"limit": 2})
        dashboard = self.client.get("/")

        self.assertEqual(skills.json()[0], {"skill": "python", "count": 2})
        self.assertEqual(
            gaps.json(),
            [{"skill": "aws", "count": 1}, {"skill": "sql", "count": 1}],
        )
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("PlacementLens UK", dashboard.text)
        self.assertIn("/api/summary", dashboard.text)


if __name__ == "__main__":
    unittest.main()
