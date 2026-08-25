import sqlite3
import unittest

from placement_lens.analytics import (
    get_ranked_jobs,
    get_skill_demand,
    get_skill_gaps,
    get_summary,
)
from placement_lens.storage import (
    initialize_database,
    load_candidate,
    load_jobs,
    load_ranking_run,
)


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        initialize_database(self.connection)
        load_jobs(
            self.connection,
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
                    "timestamp_kind": "updated",
                },
            ],
        )
        load_candidate(
            self.connection,
            {
                "candidate_id": "candidate-local",
                "target_location": "London",
                "profile_text": "Python data analysis",
                "skills": ["Python"],
            },
        )
        self.run_id = load_ranking_run(
            self.connection,
            candidate_id="candidate-local",
            model_version="hybrid-v1",
            payload={
                "ranked_jobs": [
                    {
                        "job_id": "a", "score": 62.5, "skill_coverage": 50.0,
                        "skill_confidence": 66.7, "skill_score": 33.4,
                        "title_score": 100.0, "text_score": 20.0,
                        "level_score": 100.0, "matched_skills": ["python"],
                        "missing_skills": ["sql"],
                    },
                    {
                        "job_id": "b", "score": 40.0, "skill_coverage": 57.1,
                        "skill_confidence": 66.7, "skill_score": 38.1,
                        "title_score": 0.0, "text_score": 6.0,
                        "level_score": 100.0, "matched_skills": ["python"],
                        "missing_skills": ["aws"],
                    },
                ]
            },
        )

    def tearDown(self):
        self.connection.close()

    def test_summary_and_skill_analytics(self):
        summary = get_summary(self.connection, run_id=self.run_id)

        self.assertEqual(summary["total_jobs"], 2)
        self.assertEqual(summary["sources"], 2)
        self.assertEqual(summary["target_level_jobs"], 2)
        self.assertEqual(summary["average_score"], 51.3)
        self.assertEqual(summary["latest_publication"], "2026-07-20T10:00:00Z")
        self.assertEqual(
            get_skill_demand(self.connection, limit=3),
            [
                {"skill": "python", "count": 2},
                {"skill": "aws", "count": 1},
                {"skill": "sql", "count": 1},
            ],
        )
        self.assertEqual(
            get_skill_gaps(self.connection, run_id=self.run_id, limit=2),
            [
                {"skill": "aws", "count": 1},
                {"skill": "sql", "count": 1},
            ],
        )

    def test_ranked_jobs_support_source_and_level_filters(self):
        rows = get_ranked_jobs(
            self.connection,
            run_id=self.run_id,
            source="Jobicy",
            level="Internship",
            limit=10,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["job_id"], "b")
        self.assertEqual(rows[0]["rank"], 2)
        self.assertEqual(rows[0]["matched_skills"], ["python"])
        self.assertEqual(rows[0]["missing_skills"], ["aws"])
        self.assertEqual(rows[0]["source_url"], "https://jobs.example/b")
        self.assertEqual(rows[0]["timestamp_kind"], "updated")


if __name__ == "__main__":
    unittest.main()
