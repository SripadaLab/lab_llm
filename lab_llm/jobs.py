"""Run independent LLM jobs with durable, resumable progress."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .calls import call_llm
from .config import get_model
from .progress import RunProgress, TokenPricing, add_cost_estimate
from .records import (
    append_record,
    attempt_counts,
    completed_record,
    failed_record,
    latest_by_job,
    prepare_job,
    read_records,
    validate_output,
)
from .structured import OutputContract


@dataclass
class LLMJob:
    """One independent model request with a stable ID."""

    job_id: str
    prompt: str
    instructions: Optional[str] = None
    model: Optional[str] = None
    max_output_tokens: Optional[int] = None
    output_format: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or not self.job_id.strip():
            raise ValueError("job_id must be a non-empty string")
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        if self.model is not None and (
            not isinstance(self.model, str) or not self.model.strip()
        ):
            raise ValueError("model must be a non-empty string")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
        if self.max_output_tokens is not None and (
            isinstance(self.max_output_tokens, bool)
            or not isinstance(self.max_output_tokens, int)
            or self.max_output_tokens <= 0
        ):
            raise ValueError("max_output_tokens must be a positive integer")
        if self.output_format is not None and not isinstance(
            self.output_format, dict
        ):
            raise ValueError("output_format must be a dictionary")

        # These values are written to JSONL. Check them before any API calls.
        try:
            json.dumps(self.metadata, allow_nan=False)
            json.dumps(self.output_format, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "metadata and output_format must contain JSON-compatible values"
            ) from exc


def run_jobs(
    jobs: Iterable[LLMJob],
    output_path: str | Path,
    *,
    pricing: TokenPricing | None = None,
    workers: int = 1,
    output_contract: OutputContract | None = None,
) -> list[dict[str, Any]]:
    """Run jobs and save each result immediately.

    Reusing the same output path resumes the run. Completed job IDs are
    skipped. Failed jobs are attempted again. If a job's request changed while
    keeping the same ID, the run stops before making any API calls.

    API, response, and output-validation errors are recorded. Running again
    retries failed jobs, but never completed ones. ``workers=1`` is sequential.
    Larger values use separate processes; only the parent process validates
    and writes results.
    """
    jobs = list(jobs)
    if not jobs:
        raise ValueError("jobs must contain at least one LLMJob")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("workers must be a positive integer")

    job_ids = [job.job_id for job in jobs]
    if len(job_ids) != len(set(job_ids)):
        raise ValueError("job_id values must be unique")

    # Resolve the default model once. The saved request then records exactly
    # which model was used, even if .env changes later.
    default_model = get_model() if any(job.model is None for job in jobs) else None
    prepared = [prepare_job(job, default_model, output_contract) for job in jobs]

    # Explicit pricing prevents a silent estimate for the wrong model.
    if pricing is not None:
        models = {request["model"] for _, request in prepared}
        if models != {pricing.model}:
            raise ValueError(
                f"pricing is for {pricing.model!r}, but jobs use {sorted(models)!r}"
            )

    output_path = Path(output_path)
    previous_records = read_records(output_path)
    latest = latest_by_job(previous_records)
    attempts = attempt_counts(previous_records)

    # Older run records may predate cost tracking. Enrich the in-memory copy
    # so regenerated CSV output still gets a cost estimate.
    for record in latest.values():
        if record.get("status") == "completed":
            add_cost_estimate(record, pricing)

    # A stable ID must always mean the same request. Otherwise resume could
    # silently keep an old answer for a changed prompt.
    for job, request in prepared:
        previous = latest.get(job.job_id)
        if previous and previous.get("request_hash") != request["request_hash"]:
            raise ValueError(
                f"job {job.job_id!r} changed since this run was created; "
                "use a new output path or a new job_id"
            )
        if (
            previous
            and previous.get("status") == "completed"
            and output_contract is not None
            and (
                previous.get("contract_id") != output_contract.contract_id
                or previous.get("validation_status") != "passed"
            )
        ):
            raise ValueError(
                f"job {job.job_id!r} was completed without validation by "
                f"contract {output_contract.contract_id!r}; use a new output "
                "path"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pending_jobs = sum(
        not (latest.get(job.job_id) or {}).get("status") == "completed"
        for job in jobs
    )
    progress = RunProgress(
        total_jobs=len(jobs),
        pending_jobs=pending_jobs,
        existing_records=latest.values(),
        pricing=pricing,
    )

    pending = []
    for number, (job, request) in enumerate(prepared, start=1):
        previous = latest.get(job.job_id)
        if previous and previous.get("status") == "completed":
            print(f"[{number}/{len(jobs)}] skip {job.job_id} (completed)")
            continue
        pending.append((number, job, request, attempts.get(job.job_id, 0) + 1))

    with output_path.open("a", encoding="utf-8") as output_file:
        if workers == 1:
            for number, job, request, attempt in pending:
                print(f"[{number}/{len(jobs)}] run  {job.job_id}")
                record = _run_one_job(job, request, attempt)
                _save_record(
                    record, number, len(jobs), output_file,
                    latest, attempts, progress, pricing, output_contract,
                )
        else:
            # Workers make requests. The parent remains the only process that
            # writes JSONL, so concurrent completions cannot corrupt the file.
            executor = ProcessPoolExecutor(max_workers=workers)
            futures = {}
            try:
                for number, job, request, attempt in pending:
                    print(f"[{number}/{len(jobs)}] queue {job.job_id}")
                    future = executor.submit(_run_one_job, job, request, attempt)
                    futures[future] = (number, job, request, attempt)

                for future in as_completed(futures):
                    number, job, request, attempt = futures[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        # A failed worker process is still a visible job failure.
                        record = failed_record(job, request, exc, attempt, 0.0)
                    _save_record(
                        record, number, len(jobs), output_file,
                        latest, attempts, progress, pricing, output_contract,
                    )
            except KeyboardInterrupt:
                # Do not start queued calls after the user stops the run.
                for future in futures:
                    future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                raise
            else:
                executor.shutdown()

    # Return one current record per requested job, in the original job order.
    return [latest[job.job_id] for job in jobs]


def _run_one_job(
    job: LLMJob,
    request: dict[str, Any],
    attempt: int,
) -> dict[str, Any]:
    """Make one call. Safe to execute in the parent or a worker process."""
    started_at = time.perf_counter()
    try:
        result = call_llm(
            job.prompt,
            instructions=job.instructions,
            model=request["model"],
            max_output_tokens=job.max_output_tokens,
            output_format=request["output_format"],
        )
        duration = time.perf_counter() - started_at
        return completed_record(job, request, result, attempt, duration)
    except Exception as exc:
        duration = time.perf_counter() - started_at
        return failed_record(job, request, exc, attempt, duration)


def _save_record(
    record: dict[str, Any],
    number: int,
    total: int,
    output_file,
    latest: dict[str, dict[str, Any]],
    attempts: dict[str, int],
    progress: RunProgress,
    pricing: TokenPricing | None,
    output_contract: OutputContract | None,
) -> None:
    """Save one returned record and update parent-owned progress."""
    validate_output(record, output_contract)
    add_cost_estimate(record, pricing)
    append_record(output_file, record)
    latest[record["job_id"]] = record
    attempts[record["job_id"]] = record["attempt"]
    status = progress.update(record)
    if record["status"] == "completed":
        print(f"[{number}/{total}] done {record['job_id']} | {status}")
    else:
        error_type = (record.get("error") or {}).get("type", "Error")
        print(f"[{number}/{total}] fail {record['job_id']}: {error_type} | {status}")
