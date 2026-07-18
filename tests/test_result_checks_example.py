"""Tests for the saved-result classification example."""

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "examples/09_check_results/example.py"
RESULTS = PROJECT / "data/synthetic_rating_results.jsonl"


class ResultChecksExampleTests(TestCase):
    def test_prints_all_five_outcomes(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), str(RESULTS)],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("T01-anxiety", completed.stdout)
        self.assertIn("failed              Connection timed out", completed.stdout)
        self.assertIn("validation_failed   rating: Field required", completed.stdout)
        self.assertIn("parsed              72", completed.stdout)
        self.assertIn("not_scored          None", completed.stdout)
        self.assertIn("parse_failed        117", completed.stdout)

    def test_validates_older_results_without_parsed_output(self):
        record = {
            "job_id": "T01-anxiety",
            "status": "completed",
            "output_text": '{"rating": 72}',
            "metadata": {"min_value": 0, "max_value": 100},
        }

        with TemporaryDirectory() as directory:
            path = Path(directory) / "raw_results.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertIn("parsed              72.0", completed.stdout)

    def test_validates_categorical_results(self):
        records = [
            {
                "job_id": "T01-support",
                "status": "completed",
                "parsed_output": {"rating": "Yes"},
                "metadata": {
                    "min_value": None,
                    "max_value": None,
                    "allowed_values": ["Yes", "No"],
                },
            },
            {
                "job_id": "T02-support",
                "status": "completed",
                "parsed_output": {"rating": "Maybe"},
                "metadata": {
                    "min_value": None,
                    "max_value": None,
                    "allowed_values": ["Yes", "No"],
                },
            },
        ]

        with TemporaryDirectory() as directory:
            path = Path(directory) / "raw_results.jsonl"
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertIn("parsed              Yes", completed.stdout)
        self.assertIn("parse_failed        Maybe", completed.stdout)
