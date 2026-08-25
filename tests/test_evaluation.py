import csv
import io
import tempfile
import unittest
from pathlib import Path

from placement_lens.evaluation import (
    evaluate_ranking,
    load_relevance_labels,
    write_label_template,
)


class EvaluationTests(unittest.TestCase):
    def test_perfect_ranking_scores_one_on_all_metrics(self):
        metrics = evaluate_ranking(
            ["a", "b", "c"],
            {"a": 3, "b": 2, "c": 1},
            k=3,
        )

        self.assertEqual(metrics["precision_at_k"], 1.0)
        self.assertEqual(metrics["ndcg_at_k"], 1.0)
        self.assertEqual(metrics["mrr_at_k"], 1.0)
        self.assertEqual(metrics["labeled_jobs"], 3)

    def test_unlabeled_jobs_are_excluded_from_evaluation(self):
        metrics = evaluate_ranking(
            ["unlabeled", "negative", "relevant"],
            {"negative": 0, "relevant": 2},
            k=2,
        )

        self.assertEqual(metrics["evaluated_at_k"], 2)
        self.assertEqual(metrics["precision_at_k"], 0.5)
        self.assertEqual(metrics["mrr_at_k"], 0.5)

    def test_writes_and_loads_reviewable_label_csv(self):
        payload = {
            "ranked_jobs": [
                {
                    "job_id": "a",
                    "title": "Data Analyst Intern",
                    "company": "Acme",
                    "source": "The Muse",
                    "source_url": "https://jobs.example/a",
                },
                {
                    "job_id": "b",
                    "title": "ML Engineer",
                    "company": "Beta",
                    "source": "Jobicy",
                    "source_url": "https://jobs.example/b",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "labels.csv"
            write_label_template(payload, path, limit=1)
            rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
            rows[0]["relevance"] = "3"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            labels = load_relevance_labels(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Data Analyst Intern")
        self.assertEqual(labels, {"a": 3})


if __name__ == "__main__":
    unittest.main()
