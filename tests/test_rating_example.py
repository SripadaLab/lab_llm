"""Tests for the reusable ratings batch helper."""

import argparse
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from pydantic import BaseModel, ConfigDict

from lab_llm import (
    DeidentificationResult,
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

    rating: float | str | None


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
    def test_describes_batch_deidentification_settings(self):
        self.assertEqual(
            ratings._deidentification_settings(None),
            {"enabled": False},
        )

        class FakeDeidentifier:
            device = "cpu"
            labels = {"private_person", "private_email"}
            checkpoint = "/approved/privacy-filter"
            calibration_path = None

        self.assertEqual(
            ratings._deidentification_settings(FakeDeidentifier()),
            {
                "enabled": True,
                "device": "cpu",
                "labels": ["private_email", "private_person"],
                "checkpoint": "/approved/privacy-filter",
                "calibration_path": None,
                "scope": "transcript",
            },
        )

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

    def test_rating_batch_scopes_deidentification_per_transcript(self):
        transcripts = TranscriptBank((
            Transcript("T1", "First transcript", "T1.txt"),
        ))
        items = ItemBank((Item("I1", "Rate mood", 0, 100),))
        template = PromptTemplate(
            "Item: {item}\nRequirements: {response_requirements}\n"
            "Transcript: {transcript}",
            fields=("item", "response_requirements", "transcript"),
        )
        pricing = TokenPricing(
            model="test-model",
            input_per_million=1.0,
            cached_input_per_million=0.5,
            output_per_million=2.0,
            as_of="2026-07-16",
        )
        deidentifier = Mock()
        deidentifier.device = "cpu"
        deidentifier.labels = {"private_person"}
        deidentifier.checkpoint = None
        deidentifier.calibration_path = None
        deidentifier.deidentify.return_value = DeidentificationResult(
            text="[PRIVATE_PERSON_1]",
            matches=(),
        )

        with TemporaryDirectory() as directory:
            directory = Path(directory)
            instructions = directory / "instructions.txt"
            instructions.write_text("Be careful.", encoding="utf-8")
            batch_result = [completed_record()]
            with (
                patch.object(
                    ratings.TranscriptBank,
                    "from_directory",
                    return_value=transcripts,
                ),
                patch.object(
                    ratings.ItemBank,
                    "from_csv",
                    return_value=items,
                ),
                patch.object(
                    ratings.PromptTemplate,
                    "from_file",
                    return_value=template,
                ),
                patch.object(ratings, "get_model", return_value="test-model"),
                patch.object(
                    ratings,
                    "load_token_pricing",
                    return_value=pricing,
                ),
                patch.object(ratings, "write_job_plan") as write_job_plan,
                patch.object(ratings, "write_manifest"),
                patch.object(
                    ratings,
                    "run_jobs",
                    return_value=batch_result,
                ) as run_jobs,
                patch.object(ratings, "_write_results", return_value=[]),
                patch.object(ratings, "_write_summary"),
                patch.object(ratings, "_report", return_value=0),
            ):
                exit_code = ratings.run_rating_batch(
                    Rating,
                    prompt_path=directory / "prompt.txt",
                    transcripts_path=directory / "transcripts",
                    items_path=directory / "items.csv",
                    instructions_path=instructions,
                    pricing_path=directory / "pricing.csv",
                    runs_path=directory / "runs",
                    max_output_tokens=100,
                    deidentifier=deidentifier,
                    argv=["--run-name", "scoped-privacy"],
                )

        self.assertEqual(exit_code, 0)
        deidentifier.deidentify.assert_called_once_with(
            "First transcript",
            scope="T1",
        )
        planned_job = write_job_plan.call_args.args[0][0]
        self.assertIn("First transcript", planned_job.prompt)
        safe_job = run_jobs.call_args.args[0][0]
        self.assertIn("[PRIVATE_PERSON_1]", safe_job.prompt)
        self.assertNotIn("First transcript", safe_job.prompt)
        self.assertNotIn("deidentifier", run_jobs.call_args.kwargs)
        self.assertNotIn(
            "deidentification_scope_key",
            run_jobs.call_args.kwargs,
        )
        self.assertEqual(
            run_jobs.call_args.kwargs["deidentification_by_job"][
                "transcript-T1__item-I1"
            ].text_count,
            1,
        )

    def test_builds_the_transcript_item_grid(self):
        transcripts = TranscriptBank((
            Transcript("T1", "First transcript", "T1.txt"),
            Transcript("T2", "Second transcript", "T2.txt"),
        ))
        items = ItemBank((
            Item("I1", "Rate mood", 0, 100),
            Item(
                "I2",
                "Rate agreement",
                None,
                None,
                "Strongly disagree | Disagree | Neutral | Agree | "
                "Strongly agree",
            ),
            Item(
                "I3",
                "Rate worry",
                0,
                3,
                "0 = Not at all | 1 = Several days | "
                "2 = More than half the days | 3 = Nearly every day",
            ),
            Item("I4", "Was support helpful?", None, None, "Yes | No"),
        ))
        template = PromptTemplate(
            "Item: {item}\nRequirements: {response_requirements}\n"
            "Transcript: {transcript}",
            fields=(
                "item", "response_requirements", "transcript",
            ),
        )

        jobs = ratings._build_jobs(
            transcripts,
            items,
            template,
            "Be careful.",
            CONTRACT,
            100,
        )

        self.assertEqual(len(jobs), 8)
        self.assertEqual(jobs[0].job_id, "transcript-T1__item-I1")
        self.assertEqual(jobs[-1].job_id, "transcript-T2__item-I4")
        self.assertIn("First transcript", jobs[0].prompt)
        self.assertEqual(jobs[0].metadata["transcript_file"], "T1.txt")
        self.assertIsNone(jobs[-1].metadata["max_value"])
        self.assertEqual(jobs[-1].metadata["allowed_values"], ["Yes", "No"])
        self.assertIn("Return exactly one", jobs[-1].prompt)
        self.assertNotIn("Numeric range", jobs[-1].prompt)
        self.assertEqual(jobs[0].metadata["scoring_values"], "")
        self.assertIn("Numeric range: 0 to 100.", jobs[0].prompt)
        self.assertIn("Any number in the allowed range.", jobs[0].prompt)
        rating_schemas = [
            job.output_format["schema"]["properties"]["rating"]
            for job in jobs[:4]
        ]
        self.assertEqual(rating_schemas[0]["anyOf"][0], {"type": "number"})
        self.assertEqual(rating_schemas[1]["anyOf"][0], {
            "type": "string",
            "enum": [
                "Strongly disagree",
                "Disagree",
                "Neutral",
                "Agree",
                "Strongly agree",
            ],
        })
        self.assertEqual(rating_schemas[2]["anyOf"][0], {
            "type": "integer",
            "enum": [0, 1, 2, 3],
        })
        self.assertEqual(rating_schemas[3]["anyOf"][0], {
            "type": "string",
            "enum": ["Yes", "No"],
        })
        for schema in rating_schemas:
            self.assertEqual(schema["anyOf"][-1], {"type": "null"})
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

        discrete = completed_record(2.5)
        discrete["metadata"]["allowed_values"] = [0, 1, 2, 3]
        self.assertEqual(
            ratings._rating_value(discrete),
            (None, "parse_failed", "rating must be one of: 0, 1, 2, 3"),
        )

        discrete["parsed_output"]["rating"] = 2
        self.assertEqual(
            ratings._rating_value(discrete),
            ("2", "parsed", ""),
        )

        categorical = completed_record("Yes")
        categorical["metadata"].update({
            "min_value": None,
            "max_value": None,
            "allowed_values": ["Yes", "No"],
        })
        self.assertEqual(
            ratings._rating_value(categorical),
            ("Yes", "parsed", ""),
        )

        categorical["parsed_output"]["rating"] = "Maybe"
        self.assertEqual(
            ratings._rating_value(categorical),
            (None, "parse_failed", "rating must be one of: Yes, No"),
        )

        categorical["parsed_output"]["rating"] = 1
        self.assertEqual(
            ratings._rating_value(categorical),
            (None, "parse_failed", "rating must be one of: Yes, No"),
        )

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
                settings={
                    "local_deidentification": {"enabled": True},
                },
            )
            runs.write_job_plan([job], jobs_path)
            runs.write_manifest(
                [job],
                "test-model",
                {"transcripts": source},
                pricing,
                CONTRACT,
                manifest_path,
                settings={
                    "local_deidentification": {"enabled": True},
                },
            )

            changed = LLMJob(job.job_id, "Changed prompt", model="test-model")
            with self.assertRaisesRegex(ValueError, "current jobs"):
                runs.write_job_plan([changed], jobs_path)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["expected_jobs"], 1)
        self.assertEqual(manifest["output_contract"], "rating@1")
        self.assertEqual(manifest["pricing"]["currency"], "USD")
        self.assertEqual(
            manifest["settings"]["local_deidentification"],
            {"enabled": True},
        )
