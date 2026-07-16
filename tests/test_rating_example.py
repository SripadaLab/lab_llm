"""Tests for the transparent, rating-specific sequential-ratings code."""

import csv
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from lab_llm import Item, ItemBank, PromptTemplate, Transcript, TranscriptBank


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
    def test_requires_a_safe_run_name(self):
        arguments = ratings.parse_args([
            "--run-name",
            "anxiety-pilot",
            "--pricing-file",
            "data/model_pricing.csv",
        ])
        self.assertEqual(arguments.run_name, "anxiety-pilot")
        self.assertEqual(arguments.pricing_file, Path("data/model_pricing.csv"))
        self.assertFalse(arguments.dry_run)
        self.assertEqual(arguments.workers, 1)
        self.assertEqual(arguments.transcripts, Path("data/transcripts"))
        self.assertEqual(arguments.items, Path("data/items.csv"))
        self.assertEqual(arguments.instructions, Path("data/instructions.txt"))

        dry_run = ratings.parse_args([
            "--run-name",
            "preview",
            "--pricing-file",
            "data/model_pricing.csv",
            "--dry-run",
            "--workers",
            "4",
            "--transcripts",
            "studies/anxiety/transcripts",
            "--items",
            "studies/anxiety/items.csv",
            "--instructions",
            "studies/anxiety/instructions.txt",
        ])
        self.assertTrue(dry_run.dry_run)
        self.assertEqual(dry_run.workers, 4)
        self.assertEqual(
            dry_run.transcripts,
            Path("studies/anxiety/transcripts"),
        )
        self.assertEqual(dry_run.items, Path("studies/anxiety/items.csv"))
        self.assertEqual(
            dry_run.instructions,
            Path("studies/anxiety/instructions.txt"),
        )

        for value in ("../outside", "nested/run", "", ".hidden"):
            with self.subTest(value=value):
                with self.assertRaises(ratings.argparse.ArgumentTypeError):
                    ratings.run_name_arg(value)

    def test_builds_the_complete_transcript_item_grid(self):
        transcripts = TranscriptBank((
            Transcript("T1", "First transcript", "T1.txt"),
            Transcript("T2", "Second transcript", "T2.txt"),
        ))
        items = ItemBank((
            Item("I1", "Rate mood", 0, 100),
            Item("I2", "Rate worry", 1, 5),
        ))
        template = PromptTemplate(
            "Item: {item}\nRange: {min_value}-{max_value}\n"
            "Transcript: {transcript}",
            fields=("item", "min_value", "max_value", "transcript"),
        )

        jobs = ratings.build_jobs(transcripts, items, template, "Be careful.")

        self.assertEqual(len(jobs), 4)
        self.assertEqual(jobs[0].job_id, "transcript-T1__item-I1")
        self.assertEqual(jobs[-1].job_id, "transcript-T2__item-I2")
        self.assertIn("Rate mood", jobs[0].prompt)
        self.assertIn("First transcript", jobs[0].prompt)
        self.assertEqual(jobs[0].metadata["transcript_file"], "T1.txt")
        self.assertEqual(jobs[0].metadata["min_value"], 0)
        self.assertEqual(jobs[-1].metadata["max_value"], 5)
        self.assertEqual(jobs[0].output_format, ratings.RATING_OUTPUT_FORMAT)

    def test_parses_only_structured_in_range_ratings_or_null(self):
        self.assertEqual(
            ratings.parse_rating('{"rating":42}', 0, 100),
            ("42", "parsed", ""),
        )
        self.assertEqual(
            ratings.parse_rating('{"rating":null}', 0, 100),
            (None, "not_scored", ""),
        )

        for text in (
            "42",
            '{"rating":101}',
            '{"rating":true}',
            '{"rating":42,"extra":1}',
            '{"rating":NaN}',
        ):
            with self.subTest(text=text):
                value, status, error = ratings.parse_rating(text, 0, 100)
                self.assertIsNone(value)
                self.assertEqual(status, "parse_failed")
                self.assertTrue(error)

    def test_writes_model_level_results_without_losing_raw_text(self):
        record = {
            "job_id": "transcript-T1__item-I1",
            "status": "completed",
            "metadata": {
                "transcript_id": "T1",
                "transcript_file": "T1.txt",
                "item_id": "I1",
                "min_value": 0,
                "max_value": 100,
            },
            "model": "test-model",
            "output_text": '{"rating":42}',
            "response_id": "resp_test",
            "usage": {
                "input_tokens": 10,
                "cached_input_tokens": 2,
                "output_tokens": 1,
                "total_tokens": 11,
            },
            "duration_seconds": 1.25,
            "estimated_cost_usd": 0.000011,
        }

        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.csv"
            ratings.write_results([record], path)
            with path.open(newline="", encoding="utf-8") as file:
                row = next(csv.DictReader(file))

        self.assertEqual(row["transcript_id"], "T1")
        self.assertEqual(row["transcript_file"], "T1.txt")
        self.assertEqual(row["item_id"], "I1")
        self.assertEqual(row["rating"], "42")
        self.assertEqual(row["raw_text"], '{"rating":42}')
        self.assertEqual(row["min_value"], "0")
        self.assertEqual(row["max_value"], "100")
        self.assertEqual(row["total_tokens"], "11")
        self.assertEqual(row["cached_input_tokens"], "2")
        self.assertEqual(row["duration_seconds"], "1.25")
        self.assertEqual(row["estimated_cost_usd"], "1.1e-05")

    def test_writes_failed_jobs_without_trying_to_parse_them(self):
        record = {
            "job_id": "transcript-T1__item-I1",
            "status": "failed",
            "metadata": {
                "transcript_id": "T1",
                "item_id": "I1",
                "min_value": 0,
                "max_value": 100,
            },
            "model": "test-model",
            "output_text": None,
            "response_id": None,
            "usage": None,
            "error": {"type": "RuntimeError", "message": "API unavailable"},
        }

        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.csv"
            rows = ratings.write_results([record], path)

        self.assertEqual(rows[0]["status"], "failed")
        self.assertEqual(rows[0]["parse_status"], "not_parsed")
        self.assertEqual(rows[0]["error_type"], "RuntimeError")
        self.assertEqual(rows[0]["error_message"], "API unavailable")

    def test_writes_a_compact_run_summary(self):
        records = [
            {
                "status": "completed",
                "model": "test-model-snapshot",
                "usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 2,
                    "output_tokens": 1,
                    "reasoning_tokens": 0,
                    "total_tokens": 11,
                },
                "estimated_cost_usd": 0.000011,
                "duration_seconds": 1.5,
            },
            {
                "status": "failed",
                "model": "test-model",
                "usage": None,
                "estimated_cost_usd": None,
                "duration_seconds": 0.5,
            },
        ]
        rows = [
            {"parse_status": "parsed"},
            {"parse_status": "not_parsed"},
        ]

        with TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json"
            summary = ratings.write_summary(records, rows, path, 2.25)
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(summary, saved)
        self.assertEqual(saved["jobs"], {
            "total": 2,
            "completed": 1,
            "failed": 1,
        })
        self.assertEqual(saved["tokens"]["total_tokens"], 11)
        self.assertEqual(saved["estimated_cost_usd"], 0.000011)
        self.assertEqual(saved["session_runtime_seconds"], 2.25)
        self.assertEqual(saved["workers"], 1)
        self.assertEqual(saved["request_runtime_seconds"], 2.0)

    def test_saves_jobs_and_manifest_without_overwriting_a_changed_run(self):
        job = ratings.LLMJob(
            "transcript-T1__item-I1",
            "Rendered prompt",
            instructions="Be careful.",
            model="test-model",
            metadata={"transcript_id": "T1", "item_id": "I1"},
        )

        with TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "transcripts"
            source.mkdir()
            (source / "T1.txt").write_text("Hello\n", encoding="utf-8")
            jobs_path = directory / "jobs.jsonl"
            manifest_path = directory / "manifest.json"
            pricing = ratings.lab_llm.TokenPricing(
                model="test-model",
                input_per_million=1.0,
                cached_input_per_million=0.5,
                output_per_million=2.0,
                as_of="2026-07-16",
            )

            ratings.write_jobs([job], jobs_path)
            ratings.write_manifest(
                [job],
                "test-model",
                {"transcripts": source},
                manifest_path,
                pricing,
            )

            saved_job = json.loads(jobs_path.read_text().splitlines()[0])
            manifest = json.loads(manifest_path.read_text())

            # Identical reruns keep the original files.
            ratings.write_jobs([job], jobs_path)
            ratings.write_manifest(
                [job],
                "test-model",
                {"transcripts": source},
                manifest_path,
                pricing,
            )

            changed = ratings.LLMJob(
                job.job_id,
                "Changed prompt",
                model="test-model",
            )
            with self.assertRaisesRegex(ValueError, "current jobs"):
                ratings.write_jobs([changed], jobs_path)

        self.assertEqual(saved_job["input"], "Rendered prompt")
        self.assertEqual(manifest["expected_jobs"], 1)
        self.assertEqual(manifest["run_name"], manifest_path.parent.name)
        self.assertEqual(manifest["model"], "test-model")
        self.assertEqual(manifest["pricing"]["currency"], "USD")
        transcript_files = manifest["sources"]["transcripts"]["files"]
        self.assertEqual(len(transcript_files), 1)
        self.assertIn("sha256", transcript_files[0])
