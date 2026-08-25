import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from placement_lens.cli import main
from placement_lens.matching import JobPosting


class CliTests(unittest.TestCase):
    def test_ranks_json_jobs_and_emits_explanations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_path = root / "candidate.json"
            jobs_path = root / "jobs.json"
            candidate_path.write_text(
                json.dumps({"skills": ["Python", "SQL"]}), encoding="utf-8"
            )
            jobs_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "job-b",
                            "title": "ML Placement",
                            "company": "Beta",
                            "description": "Python and AWS required.",
                        },
                        {
                            "id": "job-a",
                            "title": "Data Placement",
                            "company": "Alpha",
                            "description": "Python and SQL required.",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            exit_code = main(
                [
                    "rank",
                    "--candidate",
                    str(candidate_path),
                    "--jobs",
                    str(jobs_path),
                ],
                stdout=stdout,
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["candidate_skills"], ["python", "sql"])
        self.assertEqual(
            [item["job_id"] for item in payload["ranked_jobs"]],
            ["job-a", "job-b"],
        )
        self.assertEqual(payload["ranked_jobs"][1]["missing_skills"], ["aws"])

    def test_fetch_themuse_writes_normalized_jobs_with_provenance(self):
        captured = {}

        def fetcher(**kwargs):
            captured.update(kwargs)
            return [
                JobPosting(
                    job_id="themuse:123",
                    title="Junior Data Scientist",
                    company="Acme Analytics",
                    description="Python and SQL",
                    location="London, United Kingdom",
                    levels=("Entry Level",),
                    source="The Muse",
                    source_url="https://example.test/jobs/123",
                    published_at="2026-07-22T09:30:00Z",
                )
            ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "jobs.json"
            stdout = io.StringIO()

            exit_code = main(
                [
                    "fetch-themuse",
                    "--output",
                    str(output_path),
                    "--pages",
                    "2",
                    "--published-after",
                    "2026-01-01",
                ],
                stdout=stdout,
                themuse_fetcher=fetcher,
            )
            jobs = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["pages"], 2)
        self.assertEqual(captured["location"], "London, United Kingdom")
        self.assertEqual(captured["category"], "Data and Analytics")
        self.assertEqual(captured["published_after"], "2026-01-01")
        self.assertEqual(jobs[0]["source"], "The Muse")
        self.assertEqual(jobs[0]["source_url"], "https://example.test/jobs/123")
        self.assertEqual(jobs[0]["levels"], ["Entry Level"])
        self.assertEqual(json.loads(stdout.getvalue())["records"], 1)

    def test_rank_preserves_live_job_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_path = root / "candidate.json"
            jobs_path = root / "jobs.json"
            candidate_path.write_text(
                json.dumps({"skills": ["Python"]}), encoding="utf-8"
            )
            jobs_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "themuse:123",
                            "title": "Junior Data Scientist",
                            "company": "Acme Analytics",
                            "description": "Python required.",
                            "location": "London, United Kingdom",
                            "levels": ["Entry Level"],
                            "source": "The Muse",
                            "source_url": "https://example.test/jobs/123",
                            "published_at": "2026-07-22T09:30:00Z",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            main(
                ["rank", "--candidate", str(candidate_path), "--jobs", str(jobs_path)],
                stdout=stdout,
            )

        job = json.loads(stdout.getvalue())["ranked_jobs"][0]
        self.assertEqual(job["source"], "The Muse")
        self.assertEqual(job["source_url"], "https://example.test/jobs/123")
        self.assertEqual(job["location"], "London, United Kingdom")
        self.assertEqual(job["levels"], ["Entry Level"])
        self.assertEqual(job["published_at"], "2026-07-22T09:30:00Z")

    def test_rank_can_write_result_to_an_output_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_path = root / "candidate.json"
            jobs_path = root / "jobs.json"
            output_path = root / "ranked.json"
            candidate_path.write_text(
                json.dumps({"skills": ["Python"]}), encoding="utf-8"
            )
            jobs_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "job-1",
                            "title": "Data Placement",
                            "company": "Acme",
                            "description": "Python required.",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            exit_code = main(
                [
                    "rank",
                    "--candidate",
                    str(candidate_path),
                    "--jobs",
                    str(jobs_path),
                    "--output",
                    str(output_path),
                ],
                stdout=stdout,
            )
            ranked = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(ranked["ranked_jobs"][0]["job_id"], "job-1")
        self.assertEqual(json.loads(stdout.getvalue())["records"], 1)

    def test_rank_filters_jobs_to_requested_levels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_path = root / "candidate.json"
            jobs_path = root / "jobs.json"
            candidate_path.write_text(
                json.dumps({"skills": ["Python"]}), encoding="utf-8"
            )
            jobs_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "intern-1",
                            "title": "Data Intern",
                            "company": "Acme",
                            "description": "Python required.",
                            "levels": ["Internship"],
                        },
                        {
                            "id": "senior-1",
                            "title": "Senior Data Scientist",
                            "company": "Acme",
                            "description": "Python required.",
                            "levels": ["Senior Level"],
                        },
                    ]
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            main(
                [
                    "rank",
                    "--candidate",
                    str(candidate_path),
                    "--jobs",
                    str(jobs_path),
                    "--level",
                    "Internship",
                    "--level",
                    "Entry Level",
                ],
                stdout=stdout,
            )

        ranked = json.loads(stdout.getvalue())["ranked_jobs"]
        self.assertEqual([job["job_id"] for job in ranked], ["intern-1"])

    def test_rank_emits_advanced_profile_score_components(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_path = root / "candidate.json"
            jobs_path = root / "jobs.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "skills": ["Python"],
                        "target_levels": ["Internship"],
                        "preferred_title_terms": ["data analyst"],
                        "profile_text": "Python production data analysis",
                    }
                ),
                encoding="utf-8",
            )
            jobs_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "intern-1",
                            "title": "Data Analyst Intern",
                            "company": "Acme",
                            "description": "Python and SQL production analysis.",
                            "levels": ["Internship"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            main(
                ["rank", "--candidate", str(candidate_path), "--jobs", str(jobs_path)],
                stdout=stdout,
            )

        match = json.loads(stdout.getvalue())["ranked_jobs"][0]
        self.assertEqual(match["title_score"], 100.0)
        self.assertEqual(match["level_score"], 100.0)
        self.assertGreater(match["text_score"], 0.0)
        self.assertGreater(match["skill_confidence"], 0.0)
        self.assertIn("sql", match["missing_skills"])

    def test_fetch_jobicy_writes_eligible_jobs_with_provenance(self):
        captured = {}

        def fake_fetcher(**kwargs):
            captured.update(kwargs)
            return [
                JobPosting(
                    "jobicy:1",
                    "Junior Data Analyst",
                    "Acme",
                    "Python and SQL.",
                    location="UK",
                    levels=("Entry Level",),
                    source="Jobicy",
                    source_url="https://jobicy.example/jobs/1",
                    published_at="2026-07-20T10:00:00+00:00",
                )
            ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "jobicy.json"
            stdout = io.StringIO()
            main(
                [
                    "fetch-jobicy", "--count", "25", "--tag", "data science",
                    "--published-after", "2026-01-01", "--output", str(output),
                ],
                stdout=stdout,
                jobicy_fetcher=fake_fetcher,
            )
            records = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(captured["count"], 25)
        self.assertEqual(captured["tag"], "data science")
        self.assertEqual(captured["published_after"], "2026-01-01")
        self.assertEqual(records[0]["source"], "Jobicy")
        self.assertEqual(records[0]["source_url"], "https://jobicy.example/jobs/1")
        self.assertEqual(json.loads(stdout.getvalue())["records"], 1)

    def test_fetch_greenhouse_writes_bounded_jobs_with_update_provenance(self):
        captured = {}

        def fake_fetcher(**kwargs):
            captured.update(kwargs)
            return [
                JobPosting(
                    "greenhouse:acme:1",
                    "Data Analyst Intern",
                    "Acme",
                    "Python and SQL.",
                    location="London",
                    levels=("Internship",),
                    source="Greenhouse",
                    source_url="https://job-boards.greenhouse.io/acme/jobs/1",
                    published_at="2026-07-20T10:00:00-04:00",
                    timestamp_kind="updated",
                )
            ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "greenhouse.json"
            stdout = io.StringIO()
            main(
                [
                    "fetch-greenhouse",
                    "--updated-after", "2026-01-01",
                    "--updated-before", "2026-07-23",
                    "--output", str(output),
                ],
                stdout=stdout,
                greenhouse_fetcher=fake_fetcher,
            )
            records = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(captured["updated_after"], "2026-01-01")
        self.assertEqual(captured["updated_before"], "2026-07-23")
        self.assertEqual(records[0]["source"], "Greenhouse")
        self.assertEqual(records[0]["timestamp_kind"], "updated")
        self.assertEqual(json.loads(stdout.getvalue())["records"], 1)

    def test_merge_jobs_deduplicates_by_source_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.json"
            second = root / "second.json"
            output = root / "merged.json"
            shared = {
                "id": "a", "title": "Data Analyst", "company": "Acme",
                "description": "Python", "source": "One",
                "source_url": "https://jobs.example/shared",
            }
            first.write_text(json.dumps([shared]), encoding="utf-8")
            second.write_text(
                json.dumps([
                    dict(shared, id="duplicate"),
                    {
                        "id": "b", "title": "ML Engineer", "company": "Beta",
                        "description": "Python", "source": "Two",
                        "source_url": "https://jobs.example/unique",
                    },
                ]),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            main(
                ["merge-jobs", "--input", str(first), "--input", str(second),
                 "--output", str(output)],
                stdout=stdout,
            )
            records = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual([record["id"] for record in records], ["a", "b"])
        self.assertEqual(json.loads(stdout.getvalue())["records"], 2)

    def test_build_db_loads_jobs_candidate_and_ranking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            jobs_path = root / "jobs.json"
            candidate_path = root / "candidate.json"
            ranked_path = root / "ranked.json"
            database_path = root / "placement_lens.db"
            jobs_path.write_text(
                json.dumps([
                    {
                        "id": "a", "title": "Data Analyst", "company": "Acme",
                        "description": "Python and SQL", "location": "London",
                        "levels": ["Entry Level"], "source": "The Muse",
                        "source_url": "https://jobs.example/a",
                        "published_at": "2026-07-20T10:00:00Z",
                    }
                ]),
                encoding="utf-8",
            )
            candidate_path.write_text(
                json.dumps({
                    "candidate_id": "candidate-local",
                    "target_location": "London",
                    "profile_text": "Python data analysis",
                    "skills": ["Python"],
                }),
                encoding="utf-8",
            )
            ranked_path.write_text(
                json.dumps({
                    "ranked_jobs": [
                        {
                            "job_id": "a", "score": 60.0,
                            "skill_coverage": 50.0, "skill_confidence": 66.7,
                            "skill_score": 33.4, "title_score": 100.0,
                            "text_score": 20.0, "level_score": 100.0,
                            "matched_skills": ["python"], "missing_skills": ["sql"],
                        }
                    ]
                }),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            main(
                [
                    "build-db", "--jobs", str(jobs_path),
                    "--candidate", str(candidate_path), "--ranked", str(ranked_path),
                    "--database", str(database_path),
                ],
                stdout=stdout,
            )
            with sqlite3.connect(database_path) as connection:
                job_count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                run_count = connection.execute(
                    "SELECT COUNT(*) FROM ranking_runs"
                ).fetchone()[0]

        result = json.loads(stdout.getvalue())
        self.assertEqual(job_count, 1)
        self.assertEqual(run_count, 1)
        self.assertEqual(result["jobs"], 1)
        self.assertEqual(result["run_id"], 1)

    def test_repository_demo_supports_rank_and_database_build(self):
        repository_root = Path(__file__).resolve().parents[1]
        candidate_path = repository_root / "examples" / "candidate.demo.json"
        jobs_path = repository_root / "examples" / "jobs.demo.json"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ranked_path = root / "ranked.json"
            database_path = root / "placement_lens.db"

            rank_exit_code = main(
                [
                    "rank",
                    "--candidate",
                    str(candidate_path),
                    "--jobs",
                    str(jobs_path),
                    "--output",
                    str(ranked_path),
                ],
                stdout=io.StringIO(),
            )
            build_exit_code = main(
                [
                    "build-db",
                    "--jobs",
                    str(jobs_path),
                    "--candidate",
                    str(candidate_path),
                    "--ranked",
                    str(ranked_path),
                    "--database",
                    str(database_path),
                    "--model-version",
                    "hybrid-v1-demo",
                ],
                stdout=io.StringIO(),
            )

            with sqlite3.connect(database_path) as connection:
                job_count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[
                    0
                ]
                ranking_count = connection.execute(
                    "SELECT COUNT(*) FROM ranking_results"
                ).fetchone()[0]

        self.assertEqual(rank_exit_code, 0)
        self.assertEqual(build_exit_code, 0)
        self.assertEqual(job_count, 3)
        self.assertEqual(ranking_count, 3)

    def test_serve_uses_requested_database_host_and_port(self):
        captured = {}

        def fake_server(app, **kwargs):
            captured["app"] = app
            captured.update(kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "placement_lens.db"
            with sqlite3.connect(database_path) as connection:
                connection.execute("CREATE TABLE jobs(job_key TEXT PRIMARY KEY)")
            main(
                [
                    "serve", "--database", str(database_path),
                    "--host", "127.0.0.1", "--port", "8765",
                ],
                server_runner=fake_server,
            )

        self.assertEqual(captured["app"].title, "PlacementLens UK API")
        self.assertEqual(captured["host"], "127.0.0.1")
        self.assertEqual(captured["port"], 8765)

    def test_creates_label_template_and_evaluates_reviewed_labels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ranked_path = root / "ranked.json"
            labels_path = root / "labels.csv"
            ranked_path.write_text(
                json.dumps({
                    "ranked_jobs": [
                        {
                            "job_id": "a", "title": "Data Intern", "company": "Acme",
                            "source": "The Muse", "source_url": "https://jobs.example/a",
                        },
                        {
                            "job_id": "b", "title": "Senior Manager", "company": "Beta",
                            "source": "Jobicy", "source_url": "https://jobs.example/b",
                        },
                    ]
                }),
                encoding="utf-8",
            )
            main([
                "create-labels", "--ranked", str(ranked_path),
                "--output", str(labels_path), "--limit", "2",
            ])
            labels_path.write_text(
                "job_id,title,company,source,source_url,relevance,notes\n"
                "a,Data Intern,Acme,The Muse,https://jobs.example/a,3,Strong fit\n"
                "b,Senior Manager,Beta,Jobicy,https://jobs.example/b,0,Wrong level\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()

            main(
                [
                    "evaluate", "--ranked", str(ranked_path),
                    "--labels", str(labels_path), "--k", "2",
                ],
                stdout=stdout,
            )

        metrics = json.loads(stdout.getvalue())
        self.assertEqual(metrics["labeled_jobs"], 2)
        self.assertEqual(metrics["precision_at_k"], 0.5)
        self.assertEqual(metrics["mrr_at_k"], 1.0)


if __name__ == "__main__":
    unittest.main()
