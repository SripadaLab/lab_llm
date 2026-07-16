"""A friendly entry point for transcript-by-item rating batches."""
from __future__ import annotations

import csv
import json
import math
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel

from .config import get_model
from .inputs import ItemBank, PromptTemplate, TranscriptBank
from .jobs import LLMJob, run_jobs
from .progress import load_token_pricing
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
        fields=("item", "min_value", "max_value", "transcript"),
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
    )

    # Completed jobs survive interruptions. Failed jobs run again next time.
    started_at = time.perf_counter()
    records = run_jobs(
        jobs,
        run_dir / "raw_results.jsonl",
        pricing=pricing,
        workers=args.workers,
        output_contract=contract,
    )
    runtime = time.perf_counter() - started_at

    rows = _write_results(records, run_dir / "results.csv")
    _write_summary(records, rows, runtime, args.workers, run_dir / "summary.json")
    return _report(records, rows, run_dir)
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
                    min_value=f"{item.min_value:g}",
                    max_value=f"{item.max_value:g}",
                ),
                instructions=instructions,
                model=model,
                max_output_tokens=max_output_tokens,
                output_format=contract.output_format,
                metadata={
                    "transcript_id": transcript.transcript_id,
                    "transcript_file": transcript.filename,
                    "item_id": item.item_id,
                    "min_value": item.min_value,
                    "max_value": item.max_value,
                },
            ))
    return jobs


def _rating_value(record):
    """Apply the item-specific range after Pydantic checks the shape."""
    if record["status"] != "completed":
        return None, "not_parsed", ""

    parsed = record.get("parsed_output") or {}
    rating = parsed.get("rating")
    if rating is None:
        return None, "not_scored", ""
    if isinstance(rating, bool) or not isinstance(rating, (int, float)):
        return None, "parse_failed", "rating must be a number or null"
    if not math.isfinite(rating):
        return None, "parse_failed", "rating must be finite"

    minimum = Decimal(str(record["metadata"]["min_value"]))
    maximum = Decimal(str(record["metadata"]["max_value"]))
    value = Decimal(str(rating))
    if not minimum <= value <= maximum:
        return (
            None,
            "parse_failed",
            f"rating must be between {minimum:g} and {maximum:g}",
        )
    return f"{value:g}", "parsed", ""


def _write_results(records, path: Path):
    """Write an analysis-ready CSV without discarding raw output."""
    columns = [
        "job_id", "transcript_id", "transcript_file", "item_id",
        "min_value", "max_value", "model", "status", "rating",
        "parse_status", "parse_error", "raw_text", "response_id",
        "input_tokens", "output_tokens", "total_tokens",
        "cached_input_tokens", "duration_seconds", "estimated_cost_usd",
        "error_type", "error_message",
    ]
    rows = []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for record in records:
            rating, parse_status, parse_error = _rating_value(record)
            usage = record.get("usage") or {}
            error = record.get("error") or {}
            metadata = record["metadata"]
            row = {
                "job_id": record["job_id"],
                "transcript_id": metadata["transcript_id"],
                "transcript_file": metadata.get("transcript_file"),
                "item_id": metadata["item_id"],
                "min_value": metadata["min_value"],
                "max_value": metadata["max_value"],
                "model": record["model"],
                "status": record["status"],
                "rating": rating,
                "parse_status": parse_status,
                "parse_error": parse_error,
                "raw_text": record.get("output_text"),
                "response_id": record.get("response_id"),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
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
