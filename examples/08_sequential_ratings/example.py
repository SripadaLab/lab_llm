"""Ratings at scale: rate every transcript on every item.

Run:  ./scripts/run.sh examples/08_sequential_ratings/example.py \
        --run-name anxiety-structured-pilot \
        --pricing-file data/model_pricing.csv \
        --workers 4
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
import argparse
import csv
import hashlib
import json
import re
import time
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path

import lab_llm
from lab_llm import (
    ItemBank,
    LLMJob,
    PromptTemplate,
    TranscriptBank,
    load_token_pricing,
    run_jobs,
)
from lab_llm.config import get_model


DATA_DIR = Path("data")
MODULE_DIR = Path(__file__).parent

# One small schema. The API guarantees the shape; our parser still validates
# that the value falls inside each item's research-defined range.
RATING_OUTPUT_FORMAT = {
    "type": "json_schema",
    "name": "rating_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "rating": {
                "anyOf": [
                    {"type": "number"},
                    {"type": "null"},
                ]
            }
        },
        "required": ["rating"],
        "additionalProperties": False,
    },
}


def run_name_arg(value):
    """Accept a safe folder name, not a path."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise argparse.ArgumentTypeError(
            "use letters, numbers, dots, underscores, or hyphens"
        )
    return value


def parse_args(argv=None):
    """Read the run name from the command line."""
    parser = argparse.ArgumentParser(
        description="Rate every transcript on every survey item."
    )
    parser.add_argument(
        "--run-name",
        required=True,
        type=run_name_arg,
        help="output folder name inside runs/, for example anxiety-pilot",
    )
    parser.add_argument(
        "--pricing-file",
        required=True,
        type=Path,
        help="CSV pricing snapshot, for example data/model_pricing.csv",
    )
    parser.add_argument(
        "--transcripts",
        type=Path,
        default=DATA_DIR / "transcripts",
        help="folder containing one .txt file per transcript",
    )
    parser.add_argument(
        "--items",
        type=Path,
        default=DATA_DIR / "items.csv",
        help="CSV containing item IDs, prompts, and numeric ranges",
    )
    parser.add_argument(
        "--instructions",
        type=Path,
        default=DATA_DIR / "instructions.txt",
        help="text file containing directions shared by every request",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and preview the run without creating files or API calls",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="number of worker processes (default: 1, sequential)",
    )
    arguments = parser.parse_args(argv)
    if arguments.workers < 1:
        parser.error("--workers must be a positive integer")
    return arguments


def build_jobs(transcripts, items, template, instructions, model=None):
    """Create the transcript x item grid."""
    jobs = []
    for transcript in transcripts:
        for item in items:
            transcript_id = transcript.transcript_id
            item_id = item.item_id

            # The stable ID connects this request to its saved result.
            job_id = f"transcript-{transcript_id}__item-{item_id}"
            prompt = template.render(
                transcript=transcript.text,
                item=item.prompt,
                min_value=f"{item.min_value:g}",
                max_value=f"{item.max_value:g}",
            )
            jobs.append(LLMJob(
                job_id=job_id,
                prompt=prompt,
                instructions=instructions,
                model=model,
                max_output_tokens=100,       # guard against a runaway reply
                output_format=RATING_OUTPUT_FORMAT,
                metadata={
                    "transcript_id": transcript_id,
                    "transcript_file": transcript.filename,
                    "item_id": item_id,
                    "min_value": item.min_value,
                    "max_value": item.max_value,
                },
            ))
    return jobs


def file_hash(path):
    """Hash one input file so the run records exactly what it used."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_details(path):
    """Record one source file, or every text file in a source folder."""
    if path.is_dir():
        files = sorted(file for file in path.glob("*.txt") if file.is_file())
        return {
            "path": str(path),
            "files": [
                {"path": str(file), "sha256": file_hash(file)}
                for file in files
            ],
        }
    return {"path": str(path), "sha256": file_hash(path)}


def write_jobs(jobs, path):
    """Save every expected request before the first API call."""
    lines = []
    for job in jobs:
        record = {
            "job_id": job.job_id,
            "model": job.model,
            "instructions": job.instructions,
            "input": job.prompt,
            "max_output_tokens": job.max_output_tokens,
            "output_format": job.output_format,
            "metadata": job.metadata,
        }
        lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))

    content = "\n".join(lines) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"{path} does not match the current jobs")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_manifest(jobs, model, sources, path, pricing=None):
    """Save a small, inspectable record of this run's inputs."""
    run_details = {
        "run_name": path.parent.name,
        "model": model,
        "endpoint": "/v1/responses",
        "expected_jobs": len(jobs),
        "lab_llm_version": lab_llm.__version__,
        "pricing": pricing.as_dict() if pricing else None,
        "sources": {
            name: source_details(source)
            for name, source in sources.items()
        },
    }

    # A rerun must describe the same work. Keep the original creation time.
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))

        # Check the actual work before changing any generated metadata.
        comparable_existing = dict(existing)
        existing_sources = dict(existing.get("sources") or {})
        current_sources = run_details["sources"]
        add_pricing_source = (
            "pricing" in current_sources and "pricing" not in existing_sources
        )
        if add_pricing_source:
            comparable_existing["sources"] = {
                **existing_sources,
                "pricing": current_sources["pricing"],
            }

        core_details = {
            key: value for key, value in run_details.items() if key != "pricing"
        }
        comparable = {
            key: comparable_existing.get(key) for key in core_details
        }
        if comparable != core_details:
            raise ValueError(f"{path} does not match the current inputs")

        # Runs created before cost tracking can safely gain its metadata. It
        # describes the estimate; it does not change any model request.
        add_pricing = existing.get("pricing") is None and pricing is not None
        if add_pricing_source:
            existing["sources"] = comparable_existing["sources"]
        if add_pricing:
            existing["pricing"] = pricing.as_dict()
        elif existing.get("pricing") != run_details["pricing"]:
            raise ValueError(f"{path} does not match the current inputs")

        if add_pricing_source or add_pricing:
            path.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        **run_details,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _reject_json_constant(value):
    """Reject non-standard JSON values such as NaN and Infinity."""
    raise ValueError(f"invalid JSON constant: {value}")


def parse_rating(text, min_value, max_value):
    """Validate one structured rating against its item-defined range."""
    if not isinstance(text, str):
        return None, "parse_failed", "expected a JSON rating object"

    try:
        data = json.loads(
            text,
            parse_float=Decimal,
            parse_int=Decimal,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError):
        return None, "parse_failed", "expected a JSON rating object"

    if not isinstance(data, dict) or set(data) != {"rating"}:
        return None, "parse_failed", "expected only the rating field"

    rating = data["rating"]
    if rating is None:
        return None, "not_scored", ""
    if isinstance(rating, bool) or not isinstance(rating, Decimal):
        return None, "parse_failed", "rating must be a number or null"

    minimum = Decimal(str(min_value))
    maximum = Decimal(str(max_value))
    if not minimum <= rating <= maximum:
        return (
            None,
            "parse_failed",
            f"rating must be between {minimum:g} and {maximum:g}",
        )
    return str(rating), "parsed", ""


def write_results(records, path):
    """Write a small analysis-ready CSV while keeping raw JSONL untouched."""
    columns = [
        "job_id",
        "transcript_id",
        "transcript_file",
        "item_id",
        "min_value",
        "max_value",
        "model",
        "status",
        "rating",
        "parse_status",
        "parse_error",
        "raw_text",
        "response_id",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "duration_seconds",
        "estimated_cost_usd",
        "error_type",
        "error_message",
    ]

    rows = []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for record in records:
            if record["status"] == "completed":
                rating, parse_status, parse_error = parse_rating(
                    record["output_text"],
                    record["metadata"]["min_value"],
                    record["metadata"]["max_value"],
                )
            else:
                rating, parse_status, parse_error = None, "not_parsed", ""

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


def print_preflight(jobs, transcripts, items, model, pricing, workers=1):
    """Show the complete run shape without writing files or calling an API."""
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


def write_summary(records, rows, path, session_runtime_seconds, workers=1):
    """Save one compact run-level view for audit and handoff."""
    token_fields = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    )
    tokens = {
        field: sum(
            ((record.get("usage") or {}).get(field) or 0)
            for record in records
        )
        for field in token_fields
    }
    parse_counts = {
        status: sum(row["parse_status"] == status for row in rows)
        for status in ("parsed", "not_scored", "parse_failed", "not_parsed")
    }
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs": {
            "total": len(records),
            "completed": sum(
                record["status"] == "completed" for record in records
            ),
            "failed": sum(record["status"] == "failed" for record in records),
        },
        "parsing": parse_counts,
        "tokens": tokens,
        "estimated_cost_usd": round(
            sum(record.get("estimated_cost_usd") or 0 for record in records),
            10,
        ),
        "session_runtime_seconds": round(session_runtime_seconds, 6),
        "workers": workers,
        "request_runtime_seconds": round(
            sum(record.get("duration_seconds") or 0 for record in records),
            6,
        ),
        "models": sorted(
            {record["model"] for record in records if record.get("model")}
        ),
    }
    path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main(
    run_name,
    pricing_path,
    dry_run=False,
    workers=1,
    transcript_path=DATA_DIR / "transcripts",
    item_path=DATA_DIR / "items.csv",
    instructions_path=DATA_DIR / "instructions.txt",
):
    """Load inputs, run every rating, then write the tidy CSV."""
    run_dir = Path("runs") / run_name

    # Inputs stay separate: transcript files, item bank, and prompt template.
    prompt_path = MODULE_DIR / "prompt.txt"
    transcripts = TranscriptBank.from_directory(transcript_path)
    items = ItemBank.from_csv(item_path)
    template = PromptTemplate.from_file(
        prompt_path,
        fields=("item", "min_value", "max_value", "transcript"),
    )
    instructions = instructions_path.read_text(encoding="utf-8")
    model = get_model()
    pricing = load_token_pricing(pricing_path, model, service_tier="standard")
    jobs = build_jobs(transcripts, items, template, instructions, model)

    print(f"Prepared {len(jobs)} ratings.")
    if dry_run:
        print_preflight(jobs, transcripts, items, model, pricing, workers)
        return 0

    # Save the complete plan before making any API calls.
    write_jobs(jobs, run_dir / "jobs.jsonl")
    write_manifest(
        jobs,
        model,
        {
            "transcripts": transcript_path,
            "items": item_path,
            "prompt": prompt_path,
            "instructions": instructions_path,
            "pricing": pricing_path,
        },
        run_dir / "manifest.json",
        pricing,
    )

    # Worker processes make calls. The parent saves each returned result.
    # Run this script again after an interruption; completed jobs are skipped.
    session_started_at = time.perf_counter()
    records = run_jobs(
        jobs,
        run_dir / "raw_results.jsonl",
        pricing=pricing,
        workers=workers,
    )
    session_runtime = time.perf_counter() - session_started_at
    rows = write_results(records, run_dir / "results.csv")
    write_summary(
        records,
        rows,
        run_dir / "summary.json",
        session_runtime,
        workers,
    )

    completed = sum(record["status"] == "completed" for record in records)
    failed = len(records) - completed
    parse_failed = sum(row["parse_status"] == "parse_failed" for row in rows)
    print(f"Completed {completed}/{len(jobs)} ratings.")
    if failed:
        print(f"API failures: {failed}. Run again to retry them.")
    if parse_failed:
        print(f"Parse failures: {parse_failed}. Inspect results.csv.")
    print(f"Results: {run_dir / 'results.csv'}")
    return 1 if failed or parse_failed else 0


if __name__ == "__main__":
    arguments = parse_args()
    raise SystemExit(
        main(
            arguments.run_name,
            arguments.pricing_file,
            arguments.dry_run,
            arguments.workers,
            arguments.transcripts,
            arguments.items,
            arguments.instructions,
        )
    )
