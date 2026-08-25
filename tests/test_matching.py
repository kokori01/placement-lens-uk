import unittest

from placement_lens.matching import (
    CandidateProfile,
    JobPosting,
    extract_skills,
    rank_jobs,
    score_job,
)


class ExtractSkillsTests(unittest.TestCase):
    def test_extracts_and_normalizes_known_skills(self):
        text = "We use Python, SQL, Power BI and scikit-learn in production."

        skills = extract_skills(text)

        self.assertEqual(skills, {"python", "sql", "power bi", "scikit-learn"})

    def test_normalizes_common_skill_aliases(self):
        text = "Experience with PostgreSQL, Amazon Web Services and PyTorch is useful."

        skills = extract_skills(text)

        self.assertEqual(skills, {"postgresql", "aws", "pytorch"})

    def test_extracts_market_infrastructure_skills(self):
        text = (
            "Advanced Microsoft Excel, Microsoft Azure, Google Cloud Platform, "
            "ETL, Apache Kafka, Kubernetes, Docker and GitHub."
        )

        skills = extract_skills(text)

        self.assertEqual(
            skills,
            {"excel", "azure", "gcp", "etl", "kafka", "kubernetes", "docker", "git"},
        )

    def test_extracts_cv_evidenced_skills(self):
        text = (
            "Python, Java, C++, MATLAB App Designer and Linux. Applied exploratory "
            "data analysis, statistical correlation, data visualisation, predictive "
            "analytics, machine learning, deep learning and root cause analysis. "
            "Worked with Altium PCB design and embedded systems."
        )

        skills = extract_skills(text)

        self.assertEqual(
            skills,
            {
                "python", "java", "c++", "matlab", "linux", "data analysis",
                "exploratory data analysis",
                "correlation analysis", "data visualization", "predictive analytics",
                "machine learning", "deep learning", "root cause analysis",
                "altium designer", "pcb design", "embedded systems",
            },
        )

    def test_extracts_modern_data_and_ml_ecosystem(self):
        text = (
            "Pandas, NumPy, TensorFlow, XGBoost, PySpark, Databricks, Snowflake, "
            "dbt, Airflow, FastAPI, Streamlit, MLflow, Hugging Face, NLP, LLM, "
            "Generative AI, time-series forecasting and A/B testing."
        )

        skills = extract_skills(text)

        self.assertEqual(
            skills,
            {
                "pandas", "numpy", "tensorflow", "xgboost", "spark", "databricks",
                "snowflake", "dbt", "airflow", "fastapi", "streamlit", "mlflow",
                "hugging face", "nlp", "llm", "generative ai", "time series",
                "forecasting", "a/b testing",
            },
        )


class ScoreJobTests(unittest.TestCase):
    def test_scores_required_skill_coverage_with_explanation(self):
        candidate = CandidateProfile(skills=frozenset({"python", "sql"}))
        job = JobPosting(
            job_id="job-1",
            title="Junior Data Scientist",
            company="Example Ltd",
            description="Required: Python, SQL and AWS.",
        )

        result = score_job(candidate, job)

        self.assertEqual(result.score, 66.7)
        self.assertEqual(result.matched_skills, ("python", "sql"))
        self.assertEqual(result.missing_skills, ("aws",))

    def test_returns_zero_when_no_known_skills_are_present(self):
        candidate = CandidateProfile(skills=frozenset({"python"}))
        job = JobPosting(
            job_id="job-2",
            title="General Placement",
            company="Example Ltd",
            description="Curiosity and communication are essential.",
        )

        result = score_job(candidate, job)

        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.matched_skills, ())
        self.assertEqual(result.missing_skills, ())

    def test_ranks_jobs_by_descending_score(self):
        candidate = CandidateProfile(skills=frozenset({"python", "sql"}))
        jobs = [
            JobPosting("job-b", "ML Placement", "Beta", "Python and AWS required."),
            JobPosting("job-a", "Data Placement", "Alpha", "Python and SQL required."),
        ]

        ranked = rank_jobs(candidate, jobs)

        self.assertEqual([item.job.job_id for item in ranked], ["job-a", "job-b"])
        self.assertEqual([item.match.score for item in ranked], [100.0, 50.0])

    def test_advanced_ranking_uses_level_title_and_skill_evidence(self):
        candidate = CandidateProfile(
            skills=frozenset({"python"}),
            target_levels=frozenset({"Internship", "Entry Level"}),
            preferred_title_terms=("data analyst", "data scientist"),
            profile_text="Python production data analysis and statistical visualization.",
        )
        jobs = [
            JobPosting(
                "senior-1",
                "Senior Marketing Manager",
                "Beta",
                "Python required.",
                levels=("Senior Level",),
            ),
            JobPosting(
                "intern-1",
                "Data Analyst Intern",
                "Alpha",
                "Python, SQL and data visualization for production analytics.",
                levels=("Internship",),
            ),
        ]

        ranked = rank_jobs(candidate, jobs)

        self.assertEqual(ranked[0].job.job_id, "intern-1")
        self.assertEqual(ranked[0].match.title_score, 100.0)
        self.assertEqual(ranked[0].match.level_score, 100.0)
        self.assertEqual(ranked[1].match.skill_confidence, 33.3)
        self.assertIn("sql", ranked[0].match.missing_skills)

    def test_tfidf_text_similarity_prefers_overlapping_job_language(self):
        candidate = CandidateProfile(
            skills=frozenset(),
            profile_text=(
                "production measurement data analysis statistical correlation visualization"
            ),
        )
        jobs = [
            JobPosting(
                "sales-1",
                "Account Executive",
                "Beta",
                "Manage client contracts, sales targets and commercial accounts.",
            ),
            JobPosting(
                "data-1",
                "Operations Analyst",
                "Alpha",
                "Analyse production measurement data using statistical correlation and visualization.",
            ),
        ]

        ranked = rank_jobs(candidate, jobs)

        self.assertEqual(ranked[0].job.job_id, "data-1")
        self.assertGreater(ranked[0].match.text_score, ranked[1].match.text_score)


if __name__ == "__main__":
    unittest.main()
