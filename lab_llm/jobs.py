"""Run independent LLM jobs one at a time, with durable progress."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from .calls import LLMResult, call_llm
from .config import get_model


@dataclass
class LLMJob:
    """One independent model request with a stable ID."""

    job_id: str
    prompt: str
    instructions: Optional[str] = None
    model: Optional[str] = None
    max_output_tokens: Optional[int] = None
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

        # Metadata is written to JSONL. Check it before making any API calls.
        try:
            json.dumps(self.metadata, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must contain JSON-compatible values") from exc


def run_jobs(
    jobs: Iterable[LLMJob],
    output_path: str | Path,
) -> list[dict[str, Any]]:
    """Run jobs sequentially and save each result immediately.

    Reusing the same output path resumes the run. Completed job IDs are
    skipped. Failed jobs are attempted again. If a job's request changed while
    keeping the same ID, the run stops before making any API calls.

    API and response errors are recorded, then raised unchanged.
    """
    jobs = list(jobs)
    if not jobs:
        raise ValueError("jobs must contain at least one LLMJob")

    job_ids = [job.job_id for job in jobs]
    if len(job_ids) != len(set(job_ids)):
        raise ValueError("job_id values must be unique")

    # Resolve the default model once. The saved request then records exactly
    # which model was used, even if .env changes later.
    default_model = get_model() if any(job.model is None for job in jobs) else None
    prepared = [_prepare_job(job, default_model) for job in jobs]

    output_path = Path(output_path)
    previous_records = _read_records(output_path)
    latest = _latest_by_job(previous_records)
    attempts = _attempt_counts(previous_records)

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

    with output_path.open("a", encoding="utf-8") as output_file:
        for number, (job, request) in enumerate(prepared, start=1):
            previous = latest.get(job.job_id)
            if previous and previous.get("status") == "completed":
                print(f"[{number}/{len(jobs)}] skip {job.job_id} (completed)")
                continue

            attempt = attempts.get(job.job_id, 0) + 1
            print(f"[{number}/{len(jobs)}] run  {job.job_id}")

            try:
                result = call_llm(
                    job.prompt,
                    instructions=job.instructions,
                    model=request["model"],
                    max_output_tokens=job.max_output_tokens,
                )
                record = _completed_record(job, request, result, attempt)
            except Exception as exc:
                record = _failed_record(job, request, exc, attempt)
                _append_record(output_file, record)
                raise

            _append_record(output_file, record)
            latest[job.job_id] = record
            attempts[job.job_id] = attempt

    # Return one current record per requested job, in the original job order.
    return [latest[job.job_id] for job in jobs]


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
) -> dict[str, Any]:
    """Build one durable record from a completed call."""
    usage = None
    if result.usage is not None:
        usage = {
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "total_tokens": result.usage.total_tokens,
        }

    return {
        "job_id": job.job_id,
        "request_hash": request["request_hash"],
        "attempt": attempt,
        "status": "completed",
        "recorded_at": _now(),
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
) -> dict[str, Any]:
    """Build one durable record without hiding the original exception."""
    return {
        "job_id": job.job_id,
        "request_hash": request["request_hash"],
        "attempt": attempt,
        "status": "failed",
        "recorded_at": _now(),
        "metadata": job.metadata,
        "request": _saved_request(request),
        "model": request["model"],
        "output_text": None,
        "response_id": getattr(error, "response_id", None),
        "usage": None,
        "response": None,
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
