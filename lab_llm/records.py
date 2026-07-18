"""Durable records for resumable LLM jobs."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .calls import LLMResult
from .errors import LLMResponseError
from .structured import OutputContract


def prepare_job(job, default_model, contract=None):
    """Resolve defaults and fingerprint the exact request.

    An explicit job format may narrow the validation contract's schema. The
    contract still validates the returned JSON after the API call.
    """
    output_format = job.output_format
    if contract is not None and output_format is None:
        output_format = contract.output_format

    request = {
        "model": job.model or default_model,
        "instructions": job.instructions,
        "input": job.prompt,
        "max_output_tokens": job.max_output_tokens,
        "output_format": output_format,
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


def validate_output(record, contract: OutputContract | None) -> None:
    """Validate completed output before saving it."""
    if contract is None:
        return

    record["contract_id"] = contract.contract_id
    record["parsed_output"] = None
    if record["status"] != "completed":
        record["validation_status"] = "not_run"
        return

    try:
        parsed = contract.parse(record["output_text"])
    except ValidationError as exc:
        # Preserve the API response. The job is not complete until its output
        # passes the declared contract.
        record["status"] = "validation_failed"
        record["validation_status"] = "failed"
        record["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "request_id": None,
            "phase": "validation",
        }
        return

    record["validation_status"] = "passed"
    record["parsed_output"] = parsed.model_dump(mode="json")


def completed_record(job, request, result: LLMResult, attempt, duration):
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

    record = {
        "job_id": job.job_id,
        "request_hash": request["request_hash"],
        "attempt": attempt,
        "status": "completed",
        "recorded_at": _now(),
        "duration_seconds": round(duration, 6),
        "metadata": job.metadata,
        "request": _saved_request(request),
        "model": result.model or request["model"],
        "output_text": result.text,
        "response_id": result.response_id,
        "usage": usage,
        "response": _response_as_dict(result.response),
        "error": None,
    }
    if result.deidentification is not None:
        record["deidentification"] = result.deidentification.to_dict()
    return record


def failed_record(job, request, error: Exception, attempt, duration):
    """Build one durable failure record without hiding the exception."""
    response = error.response if isinstance(error, LLMResponseError) else None
    return {
        "job_id": job.job_id,
        "request_hash": request["request_hash"],
        "attempt": attempt,
        "status": "failed",
        "recorded_at": _now(),
        "duration_seconds": round(duration, 6),
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


def append_record(output_file, record) -> None:
    """Append and flush one record before the next call begins."""
    output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    output_file.flush()


def read_records(path: Path) -> list[dict[str, Any]]:
    """Read an existing run file and identify malformed lines."""
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


def latest_by_job(records):
    """Return the last saved attempt for each job ID."""
    return {record["job_id"]: record for record in records}


def attempt_counts(records):
    """Count prior attempts for each job ID."""
    counts = {}
    for record in records:
        job_id = record["job_id"]
        counts[job_id] = counts.get(job_id, 0) + 1
    return counts


def _saved_request(request):
    saved = {
        "model": request["model"],
        "instructions": request["instructions"],
        "input": request["input"],
        "max_output_tokens": request["max_output_tokens"],
        "output_format": request["output_format"],
    }
    if request.get("deidentification") is not None:
        saved["deidentification"] = request["deidentification"]
    return saved


def _response_as_dict(response):
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if hasattr(response, "model_dump_json"):
        return json.loads(response.model_dump_json())
    return {"repr": repr(response)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
