"""Tests for the reusable ratings batch helper."""

import argparse
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from pydantic import BaseModel, ConfigDict

from lab_llm import (
    Item,
    ItemBank,
    LLMJob,
    OutputContract,
    PromptTemplate,
    TokenPricing,
    Transcript,
    TranscriptBank,
)
from lab_llm import ratings, runs


class Rating(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    rating: float | None


CONTRACT = OutputContract("rating", "1", Rating)


def completed_record(value=42):
    return {
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
        "parsed_output": {"rating": value},
        "output_text": json.dumps({"rating": value}),
        "response_id": "resp_test",
        "usage": {
            "input_tokens": 10,
            "cached_input_tokens": 2,
            "output_tokens": 1,
            "total_tokens": 11,
        },
        "duration_seconds": 1.25,
        "estimated_cost_usd": 0.000011,
        "error": None,
    }


class RatingBatchTests(TestCase):
    def test_standard_cli_is_small_and_safe(self):
        args = runs.parse_run_args(
            ["--run-name", "anxiety-pilot"],
            transcripts_path=Path("data/transcripts"),
            items_path=Path("data/items.csv"),
            instructions_path=Path("data/instructions.txt"),
            pricing_path=Path("data/model_pricing.csv"),
        )
        self.assertEqual(args.run_name, "anxiety-pilot")
        self.assertEqual(args.pricing_file, Path("data/model_pricing.csv"))
        self.assertEqual(args.transcripts, Path("data/transcripts"))
        self.assertEqual(args.items, Path("data/items.csv"))
        self.assertEqual(args.instructions, Path("data/instructions.txt"))
        self.assertEqual(args.workers, 1)
        self.assertFalse(args.dry_run)

        overridden = runs.parse_run_args(
            [
                "--run-name", "other-study",
                "--transcripts", "studies/other/transcripts",
                "--pricing-file", "studies/other/pricing.csv",
            ],
            transcripts_path=Path("data/transcripts"),
            items_path=Path("data/items.csv"),
            instructions_path=Path("data/instructions.txt"),
            pricing_path=Path("data/model_pricing.csv"),
        )
        self.assertEqual(
            overridden.transcripts,
            Path("studies/other/transcripts"),
        )
        self.assertEqual(
            overridden.pricing_file,
            Path("studies/other/pricing.csv"),
        )

        for value in ("../outside", "nested/run", "", ".hidden"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    runs._run_name(value)

    def test_builds_the_transcript_item_grid(self):
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

        jobs = ratings._build_jobs(
            transcripts,
            items,
            template,
            "Be careful.",
            CONTRACT,
            100,
        )

        self.assertEqual(len(jobs), 4)
        self.assertEqual(jobs[0].job_id, "transcript-T1__item-I1")
        self.assertEqual(jobs[-1].job_id, "transcript-T2__item-I2")
        self.assertIn("First transcript", jobs[0].prompt)
        self.assertEqual(jobs[0].metadata["transcript_file"], "T1.txt")
        self.assertEqual(jobs[-1].metadata["max_value"], 5)
        self.assertEqual(jobs[0].output_format, CONTRACT.output_format)
        self.assertEqual(jobs[0].max_output_tokens, 100)

    def test_checks_item_specific_ranges_and_valid_nulls(self):
        self.assertEqual(
            ratings._rating_value(completed_record(42)),
            ("42", "parsed", ""),
        )
        self.assertEqual(
            ratings._rating_value(completed_record(None)),
            (None, "not_scored", ""),
        )

        for value in (101, True, float("nan")):
            with self.subTest(value=value):
                result, status, error = ratings._rating_value(
                    completed_record(value)
                )
                self.assertIsNone(result)
                self.assertEqual(status, "parse_failed")
                self.assertTrue(error)

    def test_writes_analysis_ready_results(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.csv"
            rows = ratings._write_results([completed_record()], path)
            with path.open(newline="", encoding="utf-8") as file:
                saved = next(csv.DictReader(file))

        self.assertEqual(rows[0]["rating"], "42")
        self.assertEqual(saved["transcript_id"], "T1")
        self.assertEqual(saved["rating"], "42")
        self.assertEqual(saved["raw_text"], '{"rating": 42}')
        self.assertEqual(saved["total_tokens"], "11")

    def test_writes_failed_jobs_without_parsing(self):
        record = completed_record()
        record.update({
            "status": "failed",
            "parsed_output": None,
            "output_text": None,
            "error": {"type": "RuntimeError", "message": "API unavailable"},
        })

        with TemporaryDirectory() as directory:
            rows = ratings._write_results(
                [record],
                Path(directory) / "results.csv",
            )

        self.assertEqual(rows[0]["parse_status"], "not_parsed")
        self.assertEqual(rows[0]["error_type"], "RuntimeError")

    def test_writes_parse_rate_and_run_summary(self):
        records = [
            completed_record(),
            {**completed_record(), "status": "validation_failed"},
            {**completed_record(), "status": "failed"},
        ]
        rows = [
            {"parse_status": "parsed"},
            {"parse_status": "not_parsed"},
            {"parse_status": "not_parsed"},
        ]

        with TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json"
            ratings._write_summary(records, rows, 2.25, 4, path)
            summary = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(summary["jobs"], {
            "total": 3,
            "completed": 1,
            "failed": 1,
            "validation_failed": 1,
        })
        self.assertEqual(summary["parsing"]["parse_rate"], 0.5)
        self.assertEqual(summary["workers"], 4)

    def test_run_plan_and_manifest_cannot_change_on_resume(self):
        job = LLMJob(
            "transcript-T1__item-I1",
            "Rendered prompt",
            instructions="Be careful.",
            model="test-model",
            output_format=CONTRACT.output_format,
            metadata={"transcript_id": "T1", "item_id": "I1"},
        )
        pricing = TokenPricing(
            model="test-model",
            input_per_million=1.0,
            cached_input_per_million=0.5,
            output_per_million=2.0,
            as_of="2026-07-16",
        )

        with TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "transcripts"
            source.mkdir()
            (source / "T1.txt").write_text("Hello\n", encoding="utf-8")
            jobs_path = directory / "jobs.jsonl"
            manifest_path = directory / "manifest.json"

            runs.write_job_plan([job], jobs_path)
            runs.write_manifest(
                [job],
                "test-model",
                {"transcripts": source},
                pricing,
                CONTRACT,
                manifest_path,
            )
            runs.write_job_plan([job], jobs_path)
            runs.write_manifest(
                [job],
                "test-model",
                {"transcripts": source},
                pricing,
                CONTRACT,
                manifest_path,
            )

            changed = LLMJob(job.job_id, "Changed prompt", model="test-model")
            with self.assertRaisesRegex(ValueError, "current jobs"):
                runs.write_job_plan([changed], jobs_path)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["expected_jobs"], 1)
        self.assertEqual(manifest["output_contract"], "rating@1")
        self.assertEqual(manifest["pricing"]["currency"], "USD")
