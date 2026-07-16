"""Tests for the transparent, rating-specific sequential-ratings code."""

import csv
import importlib.util
import json
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
            {"id": "T1", "file": "T1.txt", "text": "First transcript"},
            {"id": "T2", "file": "T2.txt", "text": "Second transcript"},
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
        self.assertEqual(jobs[0].metadata["transcript_file"], "T1.txt")

    def test_reads_one_transcript_per_text_file_in_filename_order(self):
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "transcript_02.txt").write_text(
                "Second transcript\n",
                encoding="utf-8",
            )
            (directory / "transcript_01.txt").write_text(
                "First transcript\n",
                encoding="utf-8",
            )
            (directory / "notes.csv").write_text("ignored", encoding="utf-8")

            transcripts = ratings.read_transcripts(directory)

        self.assertEqual(
            [transcript["id"] for transcript in transcripts],
            ["transcript_01", "transcript_02"],
        )
        self.assertEqual(transcripts[0]["file"], "transcript_01.txt")
        self.assertEqual(transcripts[0]["text"], "First transcript")

    def test_rejects_an_empty_transcript_file(self):
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            transcript = directory / "transcript_01.txt"
            transcript.write_text("  \n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "empty"):
                ratings.read_transcripts(directory)

    def test_rejects_a_folder_without_text_transcripts(self):
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "notes.csv").write_text("ignored", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "no .txt"):
                ratings.read_transcripts(directory)

    def test_rejects_unknown_or_missing_template_placeholders(self):
        transcripts = [{"id": "T1", "file": "T1.txt", "text": "Transcript"}]
        items = [{"item_id": "I1", "prompt": "Rate mood"}]

        for template, message in (
            ("{item}\n{unknown}", "unknown"),
            ("{item}", "missing"),
            ("{transcript}", "missing"),
        ):
            with self.subTest(template=template):
                with self.assertRaisesRegex(ValueError, message):
                    ratings.build_jobs(
                        transcripts,
                        items,
                        template,
                        "Be careful.",
                    )

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
            "metadata": {
                "transcript_id": "T1",
                "transcript_file": "T1.txt",
                "item_id": "I1",
            },
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
        self.assertEqual(row["transcript_file"], "T1.txt")
        self.assertEqual(row["item_id"], "I1")
        self.assertEqual(row["rating"], "42")
        self.assertEqual(row["raw_text"], "42")
        self.assertEqual(row["total_tokens"], "11")

    def test_writes_failed_jobs_without_trying_to_parse_them(self):
        record = {
            "job_id": "transcript-T1__item-I1",
            "status": "failed",
            "metadata": {"transcript_id": "T1", "item_id": "I1"},
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

            ratings.write_jobs([job], jobs_path)
            ratings.write_manifest(
                [job],
                "test-model",
                {"transcripts": source},
                manifest_path,
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
        self.assertEqual(manifest["model"], "test-model")
        transcript_files = manifest["sources"]["transcripts"]["files"]
        self.assertEqual(len(transcript_files), 1)
        self.assertIn("sha256", transcript_files[0])
