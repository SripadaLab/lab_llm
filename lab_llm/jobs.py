"""Run independent LLM jobs with durable, resumable progress."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from .calls import LLMResult, call_llm
from .config import get_model
from .errors import LLMResponseError
from .progress import RunProgress, TokenPricing, add_cost_estimate


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
) -> list[dict[str, Any]]:
    """Run jobs and save each result immediately.

    Reusing the same output path resumes the run. Completed job IDs are
    skipped. Failed jobs are attempted again. If a job's request changed while
    keeping the same ID, the run stops before making any API calls.

    API and response errors are recorded. Running again retries failed jobs,
    but never completed ones. ``workers=1`` is sequential. Larger values use
    separate processes; only the parent process writes the output file.
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
    prepared = [_prepare_job(job, default_model) for job in jobs]

    # Explicit pricing prevents a silent estimate for the wrong model.
    if pricing is not None:
        models = {request["model"] for _, request in prepared}
        if models != {pricing.model}:
            raise ValueError(
                f"pricing is for {pricing.model!r}, but jobs use {sorted(models)!r}"
            )

    output_path = Path(output_path)
    previous_records = _read_records(output_path)
    latest = _latest_by_job(previous_records)
    attempts = _attempt_counts(previous_records)

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
                    latest, attempts, progress, pricing,
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
                        record = _failed_record(job, request, exc, attempt, 0.0)
                    _save_record(
                        record, number, len(jobs), output_file,
                        latest, attempts, progress, pricing,
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
            output_format=job.output_format,
        )
        duration = time.perf_counter() - started_at
        return _completed_record(job, request, result, attempt, duration)
    except Exception as exc:
        duration = time.perf_counter() - started_at
        return _failed_record(job, request, exc, attempt, duration)


def _save_record(
    record: dict[str, Any],
    number: int,
    total: int,
    output_file,
    latest: dict[str, dict[str, Any]],
    attempts: dict[str, int],
    progress: RunProgress,
    pricing: TokenPricing | None,
) -> None:
    """Save one returned record and update parent-owned progress."""
    add_cost_estimate(record, pricing)
    _append_record(output_file, record)
    latest[record["job_id"]] = record
    attempts[record["job_id"]] = record["attempt"]
    status = progress.update(record)
    if record["status"] == "completed":
        print(f"[{number}/{total}] done {record['job_id']} | {status}")
    else:
        error_type = (record.get("error") or {}).get("type", "Error")
        print(f"[{number}/{total}] fail {record['job_id']}: {error_type} | {status}")


def _prepare_job(
    job: LLMJob,
    default_model: Optional[str],
) -> tuple[LLMJob, dict[str, Any]]:
    """Resolve defaults and fingerprint the exact request."""
    model = job.model or default_model
    request = {
        "model": model,
        "instructions": job.instructions,
        "input": job.prompt,
        "max_output_tokens": job.max_output_tokens,
        "output_format": job.output_format,
        "metadata": job.metadata,
    }
    encoded = json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    request["request_hash"] = hashlib.sha256(encoded).hexdigest()
    return job, request


def _completed_record(
    job: LLMJob,
    request: dict[str, Any],
    result: LLMResult,
    attempt: int,
    duration_seconds: float,
) -> dict[str, Any]:
    """Build one durable record from a completed call."""
    usage = None
    if result.usage is not None:
        usage = {
            "input_tokens": result.usage.input_tokens,
            "cached_input_tokens": result.usage.cached_input_tokens,
            "output_tokens": result.usage.output_tokens,
            "reasoning_tokens": result.usage.reasoning_tokens,
            "total_tokens": result.usage.total_tokens,
        }

    return {
        "job_id": job.job_id,
        "request_hash": request["request_hash"],
        "attempt": attempt,
        "status": "completed",
        "recorded_at": _now(),
        "duration_seconds": round(duration_seconds, 6),
        "metadata": job.metadata,
        "request": _saved_request(request),
        "model": result.model or request["model"],
        "output_text": result.text,
        "response_id": result.response_id,
        "usage": usage,
        "response": _response_as_dict(result.response),
        "error": None,
    }


def _failed_record(
    job: LLMJob,
    request: dict[str, Any],
    error: Exception,
    attempt: int,
    duration_seconds: float,
) -> dict[str, Any]:
    """Build one durable record without hiding the original exception."""
    # lab_llm response errors retain the complete unsuccessful API response.
    response = error.response if isinstance(error, LLMResponseError) else None
    return {
        "job_id": job.job_id,
        "request_hash": request["request_hash"],
        "attempt": attempt,
        "status": "failed",
        "recorded_at": _now(),
        "duration_seconds": round(duration_seconds, 6),
        "metadata": job.metadata,
        "request": _saved_request(request),
        "model": request["model"],
        "output_text": None,
        "response_id": getattr(error, "response_id", None),
        "usage": None,
        "response": _response_as_dict(response) if response is not None else None,
        "error": {
            "type": type(error).__name__,
            "message": str(error),
            "request_id": getattr(error, "request_id", None),
        },
    }


def _response_as_dict(response: Any) -> Any:
    """Convert an SDK response to JSON-compatible data."""
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if hasattr(response, "model_dump_json"):
        return json.loads(response.model_dump_json())

    # This fallback mainly helps small fake clients and compatible providers.
    return {"repr": repr(response)}


def _saved_request(request: dict[str, Any]) -> dict[str, Any]:
    """Keep the exact model request beside its result."""
    return {
        "model": request["model"],
        "instructions": request["instructions"],
        "input": request["input"],
        "max_output_tokens": request["max_output_tokens"],
        "output_format": request["output_format"],
    }


def _append_record(output_file, record: dict[str, Any]) -> None:
    """Append and flush one record before the next API call begins."""
    output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    output_file.flush()


def _read_records(path: Path) -> list[dict[str, Any]]:
    """Read an existing run file and report malformed lines clearly."""
    if not path.exists():
        return []

    records = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON in {path} at line {line_number}"
                ) from exc
            if not isinstance(record, dict) or not record.get("job_id"):
                raise ValueError(
                    f"invalid job record in {path} at line {line_number}"
                )
            records.append(record)
    return records


def _latest_by_job(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return the last saved attempt for each job ID."""
    return {record["job_id"]: record for record in records}


def _attempt_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Count prior attempts for each job ID."""
    counts: dict[str, int] = {}
    for record in records:
        job_id = record["job_id"]
        counts[job_id] = counts.get(job_id, 0) + 1
    return counts


def _now() -> str:
    """Return an unambiguous UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()
