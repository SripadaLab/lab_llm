"""Tests for the small durable job runner."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from pydantic import BaseModel, ConfigDict

from lab_llm import (
    LLMJob,
    LLMResponseError,
    LLMResult,
    OutputContract,
    TokenPricing,
    Usage,
    run_jobs,
)


class Rating(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    rating: float | None


RATING_CONTRACT = OutputContract("rating", "1", Rating)


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
        usage=Usage(
            input_tokens=10,
            cached_input_tokens=2,
            output_tokens=1,
            reasoning_tokens=0,
            total_tokens=11,
        ),
        response_id=response_id,
        status="completed",
    )


class JobTests(TestCase):
    def test_runs_in_order_and_saves_each_complete_response(self):
        output_format = {"type": "json_schema", "name": "rating"}
        jobs = [
            LLMJob(
                "job-1",
                "First",
                model="test-model",
                output_format=output_format,
            ),
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
        self.assertEqual(saved[0]["usage"]["cached_input_tokens"], 2)
        self.assertIn("duration_seconds", saved[0])
        self.assertEqual(saved[0]["request"]["output_format"], output_format)
        self.assertEqual(call.call_args_list[0].args, ("First",))
        self.assertEqual(
            call.call_args_list[0].kwargs["output_format"],
            output_format,
        )
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

    def test_validates_output_and_saves_plain_json(self):
        job = LLMJob("job-1", "Rate this", model="test-model")

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with patch(
                "lab_llm.jobs.call_llm",
                return_value=completed_result(text='{"rating": 3}'),
            ) as call:
                records = run_jobs(
                    [job],
                    output,
                    output_contract=RATING_CONTRACT,
                )

        record = records[0]
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["contract_id"], "rating@1")
        self.assertEqual(record["validation_status"], "passed")
        self.assertEqual(record["parsed_output"], {"rating": 3.0})
        self.assertEqual(
            call.call_args.kwargs["output_format"],
            RATING_CONTRACT.output_format,
        )

    def test_validation_failure_is_saved_and_retried_next_run(self):
        job = LLMJob("job-1", "Rate this", model="test-model")

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with patch(
                "lab_llm.jobs.call_llm",
                return_value=completed_result(text='{"wrong": 3}'),
            ):
                first = run_jobs(
                    [job],
                    output,
                    output_contract=RATING_CONTRACT,
                )

            with patch(
                "lab_llm.jobs.call_llm",
                return_value=completed_result(text='{"rating": 3}'),
            ) as call:
                second = run_jobs(
                    [job],
                    output,
                    output_contract=RATING_CONTRACT,
                )

            saved = [json.loads(line) for line in output.read_text().splitlines()]

        self.assertEqual(first[0]["status"], "validation_failed")
        self.assertEqual(first[0]["validation_status"], "failed")
        self.assertEqual(first[0]["error"]["phase"], "validation")
        self.assertEqual(first[0]["output_text"], '{"wrong": 3}')
        self.assertEqual(second[0]["status"], "completed")
        self.assertEqual(second[0]["attempt"], 2)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(len(saved), 2)

    def test_does_not_silently_accept_an_unvalidated_old_result(self):
        job = LLMJob(
            "job-1",
            "Rate this",
            model="test-model",
            output_format=RATING_CONTRACT.output_format,
        )

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with patch(
                "lab_llm.jobs.call_llm",
                return_value=completed_result(text='{"rating": 3}'),
            ):
                run_jobs([job], output)

            with patch("lab_llm.jobs.call_llm") as call:
                with self.assertRaisesRegex(ValueError, "without validation"):
                    run_jobs(
                        [job],
                        output,
                        output_contract=RATING_CONTRACT,
                    )

        call.assert_not_called()

    def test_contract_can_confirm_a_matching_job_output_format(self):
        job = LLMJob(
            "job-1",
            "Rate this",
            model="test-model",
            output_format=RATING_CONTRACT.output_format,
        )

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with patch(
                "lab_llm.jobs.call_llm",
                return_value=completed_result(text='{"rating": null}'),
            ):
                records = run_jobs(
                    [job],
                    output,
                    output_contract=RATING_CONTRACT,
                )

        self.assertEqual(records[0]["parsed_output"], {"rating": None})

    def test_rejects_an_output_format_that_disagrees_with_contract(self):
        job = LLMJob(
            "job-1",
            "Rate this",
            model="test-model",
            output_format={"type": "json_schema", "name": "other"},
        )

        with patch("lab_llm.jobs.call_llm") as call:
            with self.assertRaisesRegex(ValueError, "does not match contract"):
                run_jobs(
                    [job],
                    "unused.jsonl",
                    output_contract=RATING_CONTRACT,
                )

        call.assert_not_called()

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

    def test_multiple_workers_preserve_return_order(self):
        """Workers return records; only the parent writes them."""
        jobs = [
            LLMJob("job-1", "First", model="test-model"),
            LLMJob("job-2", "Second", model="test-model"),
        ]

        class ImmediateFuture:
            def __init__(self, value):
                self.value = value

            def result(self):
                return self.value

        class FakeExecutor:
            def __init__(self, *, max_workers):
                self.max_workers = max_workers

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def submit(self, function, *args):
                return ImmediateFuture(function(*args))

            def shutdown(self, *, wait=True, cancel_futures=False):
                pass

        call = Mock(side_effect=[
            completed_result("resp_1", "10"),
            completed_result("resp_2", "20"),
        ])

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with (
                patch("lab_llm.jobs.call_llm", call),
                patch("lab_llm.jobs.ProcessPoolExecutor", FakeExecutor),
                patch("lab_llm.jobs.as_completed", lambda futures: reversed(futures)),
            ):
                records = run_jobs(jobs, output, workers=2)
            saved = [json.loads(line) for line in output.read_text().splitlines()]

        self.assertEqual([record["job_id"] for record in records], ["job-1", "job-2"])
        self.assertEqual([record["job_id"] for record in saved], ["job-2", "job-1"])

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
            {"job_id": "job", "prompt": "text", "output_format": []},
            {
                "job_id": "job",
                "prompt": "text",
                "output_format": {"bad": {1, 2}},
            },
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    LLMJob(**kwargs)

        with patch("lab_llm.jobs.get_model") as get_model:
            with self.assertRaisesRegex(ValueError, "at least one"):
                run_jobs([], "unused.jsonl")
            with self.assertRaisesRegex(ValueError, "workers"):
                run_jobs(
                    [LLMJob("job", "text", model="test-model")],
                    "unused.jsonl",
                    workers=0,
                )
        get_model.assert_not_called()

    def test_saves_token_cost_and_prints_a_live_projection(self):
        pricing = TokenPricing(
            model="test-model",
            input_per_million=1.0,
            cached_input_per_million=0.5,
            output_per_million=2.0,
            as_of="2026-07-16",
        )
        jobs = [
            LLMJob("job-1", "First", model="test-model"),
            LLMJob("job-2", "Second", model="test-model"),
        ]

        with TemporaryDirectory() as directory:
            output = Path(directory) / "raw_results.jsonl"
            with (
                patch("lab_llm.jobs.call_llm", return_value=completed_result()),
                patch("builtins.print") as print_line,
            ):
                records = run_jobs(jobs, output, pricing=pricing)

        # (8 uncached x $1 + 2 cached x $0.50 + 1 output x $2) / 1M
        self.assertAlmostEqual(records[0]["estimated_cost_usd"], 0.000011)
        output_text = "\n".join(str(call.args[0]) for call in print_line.call_args_list)
        self.assertIn("elapsed", output_text)
        self.assertIn("ETA", output_text)
        self.assertIn("est. total", output_text)

    def test_rejects_pricing_for_a_different_model(self):
        pricing = TokenPricing(
            model="other-model",
            input_per_million=1.0,
            cached_input_per_million=0.5,
            output_per_million=2.0,
            as_of="2026-07-16",
        )
        job = LLMJob("job-1", "First", model="test-model")

        with patch("lab_llm.jobs.call_llm") as call:
            with self.assertRaisesRegex(ValueError, "pricing is for"):
                run_jobs([job], "unused.jsonl", pricing=pricing)

        call.assert_not_called()
