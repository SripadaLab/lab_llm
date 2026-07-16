"""Tests for the transparent, rating-specific sequential-ratings code."""

import csv
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


EXAMPLE_PATH = (
    Path(__file__).parents[1]
    / "examples"
    / "08_sequential_ratings"
    / "example.py"
)
SPEC = importlib.util.spec_from_file_location("sequential_ratings", EXAMPLE_PATH)
ratings = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ratings)


class RatingExampleTests(TestCase):
    def test_builds_the_complete_transcript_item_grid(self):
        transcripts = [
            {"id": "T1", "text": "First transcript"},
            {"id": "T2", "text": "Second transcript"},
        ]
        items = [
            {"item_id": "I1", "prompt": "Rate mood"},
            {"item_id": "I2", "prompt": "Rate worry"},
        ]
        template = "Item: {item}\nTranscript: {transcript}"

        jobs = ratings.build_jobs(transcripts, items, template, "Be careful.")

        self.assertEqual(len(jobs), 4)
        self.assertEqual(jobs[0].job_id, "transcript-T1__item-I1")
        self.assertEqual(jobs[-1].job_id, "transcript-T2__item-I2")
        self.assertIn("Rate mood", jobs[0].prompt)
        self.assertIn("First transcript", jobs[0].prompt)

    def test_parses_only_exact_in_range_ratings_or_na(self):
        self.assertEqual(ratings.parse_rating("42"), ("42", "parsed", ""))
        self.assertEqual(ratings.parse_rating("NA"), (None, "not_scored", ""))

        for text in ("Rating: 42", "101", "NaN"):
            with self.subTest(text=text):
                value, status, error = ratings.parse_rating(text)
                self.assertIsNone(value)
                self.assertEqual(status, "parse_failed")
                self.assertTrue(error)

    def test_writes_model_level_results_without_losing_raw_text(self):
        record = {
            "job_id": "transcript-T1__item-I1",
            "status": "completed",
            "metadata": {"transcript_id": "T1", "item_id": "I1"},
            "model": "test-model",
            "output_text": "42",
            "response_id": "resp_test",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 1,
                "total_tokens": 11,
            },
        }

        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.csv"
            ratings.write_results([record], path)
            with path.open(newline="", encoding="utf-8") as file:
                row = next(csv.DictReader(file))

        self.assertEqual(row["transcript_id"], "T1")
        self.assertEqual(row["item_id"], "I1")
        self.assertEqual(row["rating"], "42")
        self.assertEqual(row["raw_text"], "42")
        self.assertEqual(row["total_tokens"], "11")
