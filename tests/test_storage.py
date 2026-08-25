import sqlite3
import unittest

from placement_lens.storage import (
    initialize_database,
    load_candidate,
    load_jobs,
    load_ranking_run,
    top_demanded_skills,
)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        initialize_database(self.connection)
        self.jobs = [
            {
                "id": "a",
                "title": "Data Analyst",
                "company": "Acme",
                "description": "Python and SQL.",
                "location": "London, United Kingdom",
                "levels": ["Entry Level"],
                "source": "The Muse",
                "source_url": "https://jobs.example/a",
                "published_at": "2026-07-20T10:00:00Z",
            },
            {
                "id": "b",
                "title": "ML Engineer",
                "company": "Beta",
                "description": "Python on AWS.",
                "location": "UK",
                "levels": ["Internship"],
                "source": "Jobicy",
                "source_url": "https://jobs.example/b",
                "published_at": "2026-07-19T10:00:00Z",
                "timestamp_kind": "updated",
            },
        ]

    def tearDown(self):
        self.connection.close()

    def test_load_jobs_is_idempotent_and_normalizes_dimensions(self):
        load_jobs(self.connection, self.jobs)
        load_jobs(self.connection, self.jobs)

        counts = {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("sources", "jobs", "job_levels", "skills", "job_skills")
        }

        self.assertEqual(
            counts,
            {"sources": 2, "jobs": 2, "job_levels": 2, "skills": 3, "job_skills": 4},
        )
        self.assertEqual(
            top_demanded_skills(self.connection, limit=3),
            [("python", 2), ("aws", 1), ("sql", 1)],
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT timestamp_kind FROM jobs WHERE job_key = 'b'"
            ).fetchone()[0],
            "updated",
        )

    def test_loads_candidate_and_explainable_ranking_run(self):
        load_jobs(self.connection, self.jobs)
        candidate = {
            "candidate_id": "candidate-local",
            "target_location": "London, United Kingdom",
            "profile_text": "Python data analysis",
            "skills": ["Python"],
            "skill_evidence": {"python": "Professional project"},
        }
        ranked_payload = {
            "ranked_jobs": [
                {
                    "job_id": "a",
                    "score": 62.5,
                    "skill_coverage": 50.0,
                    "skill_confidence": 66.7,
                    "skill_score": 33.4,
                    "title_score": 100.0,
                    "text_score": 20.0,
                    "level_score": 100.0,
                    "matched_skills": ["python"],
                    "missing_skills": ["sql"],
                },
                {
                    "job_id": "b",
                    "score": 40.0,
                    "skill_coverage": 57.1,
                    "skill_confidence": 66.7,
                    "skill_score": 38.1,
                    "title_score": 0.0,
                    "text_score": 6.0,
                    "level_score": 100.0,
                    "matched_skills": ["python"],
                    "missing_skills": ["aws"],
                },
            ]
        }

        load_candidate(self.connection, candidate)
        run_id = load_ranking_run(
            self.connection,
            candidate_id="candidate-local",
            payload=ranked_payload,
            model_version="hybrid-v1",
        )

        candidate_skills = self.connection.execute(
            """
            SELECT s.name, cs.evidence
            FROM candidate_skills cs
            JOIN skills s ON s.skill_id = cs.skill_id
            WHERE cs.candidate_id = ?
            """,
            ("candidate-local",),
        ).fetchall()
        results = self.connection.execute(
            """
            SELECT rank_position, job_key, overall_score
            FROM ranking_results
            WHERE run_id = ?
            ORDER BY rank_position
            """,
            (run_id,),
        ).fetchall()
        statuses = self.connection.execute(
            """
            SELECT s.name, rrs.status
            FROM ranking_result_skills rrs
            JOIN skills s ON s.skill_id = rrs.skill_id
            WHERE rrs.run_id = ? AND rrs.job_key = 'a'
            ORDER BY s.name
            """,
            (run_id,),
        ).fetchall()

        self.assertEqual(candidate_skills, [("python", "Professional project")])
        self.assertEqual(results, [(1, "a", 62.5), (2, "b", 40.0)])
        self.assertEqual(statuses, [("python", "matched"), ("sql", "missing")])


if __name__ == "__main__":
    unittest.main()
