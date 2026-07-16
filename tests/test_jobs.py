"""Tests for the small sequential job runner."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from lab_llm import LLMJob, LLMResponseError, LLMResult, Usage, run_jobs


class FakeResponse:
    """The one SDK behavior the runner needs for raw-response storage."""

    def __init__(self, response_id, text):
        self.id = response_id
        self.output_text = text

    def model_dump(self, *, mode):
        assert mode == "json"
        return {"id": self.id, "output_text": self.output_text}


def completed_result(response_id="resp_test", text="42"):
    """Build a completed result without making an API call."""
    response = FakeResponse(response_id, text)
    return LLMResult(
        text=text,
        response=response,
        model="test-model",
        usage=Usage(input_tokens=10, output_tokens=1, total_tokens=11),
        response_id=response_id,
        status="completed",
    )


class JobTests(TestCase):
    def test_runs_in_order_and_saves_each_complete_response(self):
        jobs = [
            LLMJob("job-1", "First", model="test-model"),
            LLMJob("job-2", "Second", model="test-model"),
        ]
        call = Mock(side_effect=[
            completed_result("resp_1", "10"),
            completed_result("resp_2", "20"),
        ])

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with patch("lab_llm.jobs.call_llm", call):
                records = run_jobs(jobs, output)

            saved = [json.loads(line) for line in output.read_text().splitlines()]

        self.assertEqual([record["job_id"] for record in records], ["job-1", "job-2"])
        self.assertEqual([record["status"] for record in saved], ["completed", "completed"])
        self.assertEqual(saved[0]["response"], {"id": "resp_1", "output_text": "10"})
        self.assertEqual(saved[0]["usage"]["total_tokens"], 11)
        self.assertEqual(call.call_args_list[0].args, ("First",))
        self.assertEqual(call.call_args_list[1].args, ("Second",))

    def test_second_run_skips_completed_jobs(self):
        job = LLMJob("job-1", "Rate this", model="test-model")

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with patch(
                "lab_llm.jobs.call_llm",
                return_value=completed_result(),
            ):
                first = run_jobs([job], output)

            with patch("lab_llm.jobs.call_llm") as call:
                second = run_jobs([job], output)

            saved_lines = output.read_text().splitlines()

        call.assert_not_called()
        self.assertEqual(second, first)
        self.assertEqual(len(saved_lines), 1)

    def test_records_failure_then_retries_it_on_the_next_run(self):
        job = LLMJob("job-1", "Rate this", model="test-model")
        error = RuntimeError("temporary failure")

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"

            with patch("lab_llm.jobs.call_llm", side_effect=error):
                records = run_jobs([job], output)

            failed = json.loads(output.read_text().splitlines()[0])

            with patch(
                "lab_llm.jobs.call_llm",
                return_value=completed_result(),
            ):
                retried = run_jobs([job], output)

            saved = [json.loads(line) for line in output.read_text().splitlines()]

        self.assertEqual(records[0]["status"], "failed")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"]["type"], "RuntimeError")
        self.assertEqual(retried[0]["status"], "completed")
        self.assertEqual(retried[0]["attempt"], 2)
        self.assertEqual(len(saved), 2)

    def test_failure_does_not_block_later_jobs(self):
        jobs = [
            LLMJob("job-1", "First", model="test-model"),
            LLMJob("job-2", "Second", model="test-model"),
            LLMJob("job-3", "Third", model="test-model"),
        ]
        call = Mock(side_effect=[
            completed_result("resp_1", "10"),
            RuntimeError("bad job"),
            completed_result("resp_3", "30"),
        ])

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with patch("lab_llm.jobs.call_llm", call):
                records = run_jobs(jobs, output)

        self.assertEqual(call.call_count, 3)
        self.assertEqual(
            [record["status"] for record in records],
            ["completed", "failed", "completed"],
        )

    def test_failed_response_record_keeps_the_complete_response(self):
        response = FakeResponse("resp_failed", "")
        error = LLMResponseError(response)
        job = LLMJob("job-1", "Rate this", model="test-model")

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with patch("lab_llm.jobs.call_llm", side_effect=error):
                records = run_jobs([job], output)

        self.assertEqual(records[0]["response_id"], "resp_failed")
        self.assertEqual(
            records[0]["response"],
            {"id": "resp_failed", "output_text": ""},
        )

    def test_rejects_changed_or_duplicate_jobs_before_calling_api(self):
        original = LLMJob("job-1", "Original", model="test-model")

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with patch(
                "lab_llm.jobs.call_llm",
                return_value=completed_result(),
            ):
                run_jobs([original], output)

            changed = LLMJob("job-1", "Changed", model="test-model")
            with patch("lab_llm.jobs.call_llm") as call:
                with self.assertRaisesRegex(ValueError, "changed"):
                    run_jobs([changed], output)
                with self.assertRaisesRegex(ValueError, "unique"):
                    run_jobs([original, original], output)

        call.assert_not_called()

    def test_validates_jobs_before_running(self):
        for kwargs in (
            {"job_id": "", "prompt": "text"},
            {"job_id": "job", "prompt": ""},
            {"job_id": "job", "prompt": "text", "model": ""},
            {"job_id": "job", "prompt": "text", "metadata": []},
            {"job_id": "job", "prompt": "text", "max_output_tokens": 0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    LLMJob(**kwargs)

        with patch("lab_llm.jobs.get_model") as get_model:
            with self.assertRaisesRegex(ValueError, "at least one"):
                run_jobs([], "unused.jsonl")
        get_model.assert_not_called()
