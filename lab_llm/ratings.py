"""A friendly entry point for transcript-by-item rating batches."""
from __future__ import annotations

import csv
import json
import math
import time
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel

from .config import get_model
from .inputs import ItemBank, PromptTemplate, TranscriptBank
from .jobs import LLMJob, run_jobs
from .progress import load_token_pricing
from .privacy import Deidentifier
from .runs import parse_run_args, write_job_plan, write_manifest
from .structured import OutputContract


def run_rating_batch(
    output_type: type[BaseModel],
    *,
    prompt_path: str | Path,
    transcripts_path: str | Path,
    items_path: str | Path,
    instructions_path: str | Path,
    pricing_path: str | Path,
    runs_path: str | Path,
    max_output_tokens: int,
    deidentifier: Deidentifier | None = None,
    argv: Sequence[str] | None = None,
) -> int:
    """Run one transcript-by-item rating study from the command line.

    The function call shows the study inputs. Command-line flags can override
    their paths and supply the run name and worker count.
    """
    if not isinstance(output_type, type) or not issubclass(output_type, BaseModel):
        raise TypeError("output_type must be a Pydantic BaseModel class")
    if "rating" not in output_type.model_fields:
        raise ValueError("output_type must define a rating field")

    prompt_path = Path(prompt_path)
    args = parse_run_args(
        argv,
        transcripts_path=Path(transcripts_path),
        items_path=Path(items_path),
        instructions_path=Path(instructions_path),
        pricing_path=Path(pricing_path),
    )
    run_dir = Path(runs_path) / args.run_name

    # Inputs stay separate and inspectable.
    transcripts = TranscriptBank.from_directory(args.transcripts)
    items = ItemBank.from_csv(args.items)
    template = PromptTemplate.from_file(
        prompt_path,
        fields=(
            "item",
            "response_requirements",
            "transcript",
        ),
    )
    instructions = args.instructions.read_text(encoding="utf-8")
    model = get_model()
    pricing = load_token_pricing(args.pricing_file, model)
    contract = OutputContract("rating", "1", output_type)
    jobs = _build_jobs(
        transcripts,
        items,
        template,
        instructions,
        contract,
        max_output_tokens,
        model,
    )

    print(f"Prepared {len(jobs)} ratings.")
    print(
        "Local de-identification: "
        + (
            "ON (per transcript, before API calls)"
            if deidentifier is not None
            else "OFF"
        )
    )
    if args.dry_run:
        _print_preflight(jobs, transcripts, items, model, pricing, args.workers)
        return 0

    sources = {
        "transcripts": args.transcripts,
        "items": args.items,
        "prompt": prompt_path,
        "instructions": args.instructions,
        "pricing": args.pricing_file,
    }
    write_job_plan(jobs, run_dir / "jobs.jsonl")
    write_manifest(
        jobs,
        model,
        sources,
        pricing,
        contract,
        run_dir / "manifest.json",
        settings={
            "local_deidentification": _deidentification_settings(deidentifier),
        },
    )

    # Completed jobs survive interruptions. Failed jobs run again next time.
    started_at = time.perf_counter()
    run_options = {
        "pricing": pricing,
        "workers": args.workers,
        "output_contract": contract,
    }
    jobs_to_run = jobs
    if deidentifier is not None:
        filtered_transcripts, privacy_by_transcript = _deidentify_transcripts(
            transcripts,
            deidentifier,
        )
        jobs_to_run = _build_jobs(
            filtered_transcripts,
            items,
            template,
            instructions,
            contract,
            max_output_tokens,
            model,
        )
        run_options["deidentification_by_job"] = {
            job.job_id: privacy_by_transcript[job.metadata["transcript_id"]]
            for job in jobs_to_run
        }
    records = run_jobs(
        jobs_to_run,
        run_dir / "raw_results.jsonl",
        **run_options,
    )
    runtime = time.perf_counter() - started_at

    rows = _write_results(records, run_dir / "results.csv")
    _write_summary(records, rows, runtime, args.workers, run_dir / "summary.json")
    return _report(records, rows, run_dir)


def _deidentification_settings(deidentifier):
    """Describe the privacy mode without retaining detected identifiers."""
    if deidentifier is None:
        return {"enabled": False}
    return {
        "enabled": True,
        "device": deidentifier.device,
        "labels": sorted(deidentifier.labels),
        "checkpoint": deidentifier.checkpoint,
        "calibration_path": deidentifier.calibration_path,
        "scope": "transcript",
    }


def _deidentify_transcripts(transcripts, deidentifier):
    """Filter only transcript data, with one placeholder map per transcript."""
    filtered = []
    summaries = {}
    for transcript in transcripts:
        result = deidentifier.deidentify(
            transcript.text,
            scope=transcript.transcript_id,
        )
        filtered.append(replace(transcript, text=result.text))
        summaries[transcript.transcript_id] = result.summary
    return TranscriptBank(tuple(filtered)), summaries


def _build_jobs(
    transcripts,
    items,
    template,
    instructions,
    contract,
    max_output_tokens,
    model=None,
):
    """Create the transcript x item grid."""
    jobs = []
    for transcript in transcripts:
        for item in items:
            jobs.append(LLMJob(
                job_id=(
                    f"transcript-{transcript.transcript_id}"
                    f"__item-{item.item_id}"
                ),
                prompt=template.render(
                    transcript=transcript.text,
                    item=item.prompt,
                    response_requirements=item.response_requirements,
                ),
                instructions=instructions,
                model=model,
                max_output_tokens=max_output_tokens,
                output_format=_output_format_for_item(contract, item),
                metadata={
                    "transcript_id": transcript.transcript_id,
                    "transcript_file": transcript.filename,
                    "item_id": item.item_id,
                    "min_value": item.min_value,
                    "max_value": item.max_value,
                    "scoring_values": item.scoring_values,
                    "allowed_values": list(item.allowed_values),
                },
            ))
    return jobs


def _output_format_for_item(contract, item):
    """Narrow the shared rating contract to this item's exact response set."""
    output_format = deepcopy(contract.output_format)
    properties = output_format.get("schema", {}).get("properties", {})
    base_rating_schema = properties.get("rating")
    if base_rating_schema is None:
        raise ValueError("output contract schema must define a rating property")

    if item.acceptable_responses:
        value_schema = {
            "type": "string",
            "enum": list(item.acceptable_responses),
        }
    elif item.value_labels:
        values = [value for value, _ in item.value_labels]
        integers_only = all(value.is_integer() for value in values)
        value_schema = {
            "type": "integer" if integers_only else "number",
            "enum": [
                int(value) if integers_only else value
                for value in values
            ],
        }
    else:
        value_schema = {"type": "number"}

    properties["rating"] = {
        "anyOf": [value_schema, {"type": "null"}],
        "title": base_rating_schema.get("title", "Rating"),
    }
    return output_format


def _rating_value(record):
    """Apply the item-specific range after Pydantic checks the shape."""
    if record["status"] != "completed":
        return None, "not_parsed", ""

    parsed = record.get("parsed_output") or {}
    rating = parsed.get("rating")
    if rating is None:
        return None, "not_scored", ""
    allowed = record["metadata"].get("allowed_values", [])
    if isinstance(rating, str):
        text_choices = [value for value in allowed if isinstance(value, str)]
        if not text_choices:
            return None, "parse_failed", "rating must be a number or null"
        if rating not in text_choices:
            choices = ", ".join(text_choices)
            return None, "parse_failed", f"rating must be one of: {choices}"
        return rating, "parsed", ""

    if isinstance(rating, bool) or not isinstance(rating, (int, float)):
        return None, "parse_failed", "rating must be a number, text, or null"
    if not math.isfinite(rating):
        return None, "parse_failed", "rating must be finite"

    minimum_raw = record["metadata"].get("min_value")
    maximum_raw = record["metadata"].get("max_value")
    if minimum_raw is None or maximum_raw is None:
        choices = ", ".join(str(value) for value in allowed)
        return None, "parse_failed", f"rating must be one of: {choices}"

    minimum = Decimal(str(minimum_raw))
    maximum = Decimal(str(maximum_raw))
    value = Decimal(str(rating))
    if not minimum <= value <= maximum:
        return (
            None,
            "parse_failed",
            f"rating must be between {minimum:g} and {maximum:g}",
        )
    numeric_choices = [
        Decimal(str(number))
        for number in allowed
        if isinstance(number, (int, float)) and not isinstance(number, bool)
    ]
    if numeric_choices and value not in numeric_choices:
        choices = ", ".join(f"{number:g}" for number in numeric_choices)
        return None, "parse_failed", f"rating must be one of: {choices}"
    return f"{value:g}", "parsed", ""


def _response_mode(metadata):
    """Describe the machine-level response shape saved for analysis."""
    allowed = metadata.get("allowed_values") or []
    if allowed and all(isinstance(value, str) for value in allowed):
        return "text_enum"
    if allowed and all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in allowed
    ):
        return "numeric_enum"
    if (
        metadata.get("min_value") is not None
        and metadata.get("max_value") is not None
    ):
        return "numeric_range"
    return "unknown"


def _numeric_rating_label(metadata, rating):
    """Look up the declared label for one valid numeric enum value."""
    if isinstance(rating, bool) or not isinstance(rating, (int, float)):
        return None
    scoring_values = metadata.get("scoring_values") or ""
    if not isinstance(scoring_values, str) or "=" not in scoring_values:
        return None

    rating_value = Decimal(str(rating))
    for entry in scoring_values.split("|"):
        number, separator, label = entry.partition("=")
        if not separator or not number.strip() or not label.strip():
            return None
        try:
            scoring_value = Decimal(number.strip())
        except InvalidOperation:
            return None
        if rating_value == scoring_value:
            return label.strip()
    return None


def _write_results(records, path: Path):
    """Write an analysis-ready CSV without discarding raw output."""
    columns = [
        "job_id", "transcript_id", "transcript_file", "item_id",
        "response_mode", "min_value", "max_value", "scoring_values",
        "allowed_values", "model", "status", "rating", "rating_numeric",
        "rating_text", "rating_label", "parse_status", "parse_error",
        "raw_text", "response_id", "input_tokens", "output_tokens",
        "reasoning_tokens", "total_tokens", "cached_input_tokens",
        "duration_seconds", "estimated_cost_usd", "error_type",
        "error_message",
    ]
    rows = []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for record in records:
            rating, parse_status, parse_error = _rating_value(record)
            parsed_rating = (record.get("parsed_output") or {}).get("rating")
            usage = record.get("usage") or {}
            error = record.get("error") or {}
            metadata = record["metadata"]
            rating_numeric = None
            rating_text = None
            rating_label = None
            if parse_status == "parsed":
                if isinstance(parsed_rating, str):
                    rating_text = parsed_rating
                elif (
                    isinstance(parsed_rating, (int, float))
                    and not isinstance(parsed_rating, bool)
                ):
                    rating_numeric = parsed_rating
                    rating_label = _numeric_rating_label(
                        metadata,
                        parsed_rating,
                    )
            row = {
                "job_id": record["job_id"],
                "transcript_id": metadata["transcript_id"],
                "transcript_file": metadata.get("transcript_file"),
                "item_id": metadata["item_id"],
                "response_mode": _response_mode(metadata),
                "min_value": metadata.get("min_value"),
                "max_value": metadata.get("max_value"),
                "scoring_values": metadata.get("scoring_values", ""),
                "allowed_values": json.dumps(
                    metadata.get("allowed_values") or [],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "model": record["model"],
                "status": record["status"],
                "rating": rating,
                "rating_numeric": rating_numeric,
                "rating_text": rating_text,
                "rating_label": rating_label,
                "parse_status": parse_status,
                "parse_error": parse_error,
                "raw_text": record.get("output_text"),
                "response_id": record.get("response_id"),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "reasoning_tokens": usage.get("reasoning_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "cached_input_tokens": usage.get("cached_input_tokens"),
                "duration_seconds": record.get("duration_seconds"),
                "estimated_cost_usd": record.get("estimated_cost_usd"),
                "error_type": error.get("type"),
                "error_message": error.get("message"),
            }
            writer.writerow(row)
            rows.append(row)
    return rows


def _write_summary(records, rows, runtime, workers, path: Path) -> None:
    """Save a compact run-level view for audit and handoff."""
    statuses = ("parsed", "not_scored", "parse_failed", "not_parsed")
    parsing = {
        status: sum(row["parse_status"] == status for row in rows)
        for status in statuses
    }
    completed = sum(record["status"] == "completed" for record in records)
    validation_failed = sum(
        record["status"] == "validation_failed" for record in records
    )
    returned = completed + validation_failed
    valid = parsing["parsed"] + parsing["not_scored"]
    parsing["parse_rate"] = round(valid / returned, 6) if returned else None

    token_fields = (
        "input_tokens", "cached_input_tokens", "output_tokens",
        "reasoning_tokens", "total_tokens",
    )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs": {
            "total": len(records),
            "completed": completed,
            "failed": sum(record["status"] == "failed" for record in records),
            "validation_failed": validation_failed,
        },
        "parsing": parsing,
        "tokens": {
            field: sum(
                ((record.get("usage") or {}).get(field) or 0)
                for record in records
            )
            for field in token_fields
        },
        "estimated_cost_usd": round(
            sum(record.get("estimated_cost_usd") or 0 for record in records),
            10,
        ),
        "session_runtime_seconds": round(runtime, 6),
        "request_runtime_seconds": round(
            sum(record.get("duration_seconds") or 0 for record in records),
            6,
        ),
        "workers": workers,
        "models": sorted(
            {record["model"] for record in records if record.get("model")}
        ),
    }
    path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _print_preflight(jobs, transcripts, items, model, pricing, workers) -> None:
    print("Preflight passed.")
    print(f"Model: {model}")
    print(f"Pricing: {pricing.service_tier}, {pricing.as_of}")
    print(f"Transcripts: {len(transcripts)}")
    print(f"Items: {len(items)}")
    print(f"Requests: {len(jobs)}")
    print(f"Workers: {workers}")
    print(f"First job: {jobs[0].job_id}")
    print("First rendered prompt:")
    print(jobs[0].prompt)
    print("No API calls made.")


def _report(records, rows, run_dir: Path) -> int:
    completed = sum(record["status"] == "completed" for record in records)
    failed = sum(record["status"] == "failed" for record in records)
    invalid = sum(record["status"] == "validation_failed" for record in records)
    out_of_range = sum(row["parse_status"] == "parse_failed" for row in rows)

    print(f"Completed {completed}/{len(records)} ratings.")
    if failed:
        print(f"API failures: {failed}. Run again to retry them.")
    if invalid:
        print(f"Validation failures: {invalid}. Run again to retry them.")
    if out_of_range:
        print(f"Research-rule failures: {out_of_range}. Inspect results.csv.")
    print(f"Results: {run_dir / 'results.csv'}")
    return 1 if failed or invalid or out_of_range else 0
