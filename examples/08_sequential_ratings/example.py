"""Sequential ratings: rate every transcript on every item, one call at a time.

Run:  ./scripts/run.sh examples/08_sequential_ratings/example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter

import lab_llm
from lab_llm import LLMJob, run_jobs
from lab_llm.config import get_model


DATA_DIR = Path("data")
MODULE_DIR = Path(__file__).parent
RUN_DIR = Path("runs/08_sequential_ratings")


def read_table(path, required_columns):
    """Read a CSV and reject missing columns or blank cells."""
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        columns = set(reader.fieldnames or [])
        missing = set(required_columns) - columns
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing columns: {names}")

        rows = list(reader)

    if not rows:
        raise ValueError(f"{path} has no data rows")

    for row_number, row in enumerate(rows, start=2):
        for column in required_columns:
            if not (row.get(column) or "").strip():
                raise ValueError(f"{path}:{row_number} has a blank {column}")

    return rows


def read_transcripts(directory):
    """Read one plain-text transcript per file, ordered by filename."""
    if not directory.is_dir():
        raise ValueError(f"{directory} is not a directory")

    files = sorted(path for path in directory.glob("*.txt") if path.is_file())
    if not files:
        raise ValueError(f"{directory} contains no .txt transcript files")

    transcripts = []
    for path in files:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"{path} is empty")
        transcripts.append({
            "id": path.stem,       # transcript_03.txt -> transcript_03
            "file": path.name,
            "text": text,
        })
    return transcripts


def require_unique(rows, column, path):
    """Catch duplicate IDs before they can overwrite or skip a rating."""
    values = [row[column] for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"{path} contains duplicate {column} values")


def validate_template(template):
    """Allow only the two placeholders this example knows how to fill."""
    if not template.strip():
        raise ValueError("prompt template is empty")

    try:
        parts = list(Formatter().parse(template))
    except ValueError as exc:
        raise ValueError(f"invalid prompt template: {exc}") from exc

    fields = []
    for _, field, format_spec, conversion in parts:
        if field is None:
            continue
        if field not in {"item", "transcript"}:
            raise ValueError(f"unknown prompt placeholder: {{{field}}}")
        if format_spec or conversion:
            raise ValueError("prompt placeholders cannot use formatting options")
        fields.append(field)

    missing = {"item", "transcript"} - set(fields)
    if missing:
        names = ", ".join(f"{{{name}}}" for name in sorted(missing))
        raise ValueError(f"prompt template is missing: {names}")


def build_jobs(transcripts, items, template, instructions, model=None):
    """Create the transcript x item grid."""
    validate_template(template)

    jobs = []
    for transcript in transcripts:
        for item in items:
            transcript_id = transcript["id"]
            item_id = item["item_id"]

            # The stable ID connects this request to its saved result.
            job_id = f"transcript-{transcript_id}__item-{item_id}"
            prompt = template.format(
                transcript=transcript["text"],
                item=item["prompt"],
            )
            jobs.append(LLMJob(
                job_id=job_id,
                prompt=prompt,
                instructions=instructions,
                model=model,
                max_output_tokens=100,       # guard against a runaway reply
                metadata={
                    "transcript_id": transcript_id,
                    "transcript_file": transcript["file"],
                    "item_id": item_id,
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


def write_manifest(jobs, model, sources, path):
    """Save a small, inspectable record of this run's inputs."""
    run_details = {
        "model": model,
        "endpoint": "/v1/responses",
        "expected_jobs": len(jobs),
        "lab_llm_version": lab_llm.__version__,
        "sources": {
            name: source_details(source)
            for name, source in sources.items()
        },
    }

    # A rerun must describe the same work. Keep the original creation time.
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        comparable = {key: existing.get(key) for key in run_details}
        if comparable != run_details:
            raise ValueError(f"{path} does not match the current inputs")
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


def parse_rating(text):
    """Parse only an exact number from 0 to 100, or the exact text NA."""
    if not isinstance(text, str):
        return None, "parse_failed", "expected one number or NA"

    text = text.strip()
    if text == "NA":
        return None, "not_scored", ""

    try:
        rating = Decimal(text)
    except InvalidOperation:
        return None, "parse_failed", "expected one number or NA"

    if not rating.is_finite() or not 0 <= rating <= 100:
        return None, "parse_failed", "rating must be between 0 and 100"
    return str(rating), "parsed", ""


def write_results(records, path):
    """Write a small analysis-ready CSV while keeping raw JSONL untouched."""
    columns = [
        "job_id",
        "transcript_id",
        "transcript_file",
        "item_id",
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
                    record["output_text"]
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
                "error_type": error.get("type"),
                "error_message": error.get("message"),
            }
            writer.writerow(row)
            rows.append(row)

    return rows


def main():
    """Load inputs, run every rating, then write the tidy CSV."""
    # Inputs stay separate: transcript files, item bank, and prompt template.
    transcript_path = DATA_DIR / "transcripts"
    item_path = DATA_DIR / "items.csv"
    prompt_path = MODULE_DIR / "prompt.txt"
    instructions_path = DATA_DIR / "instructions.txt"
    transcripts = read_transcripts(transcript_path)
    items = read_table(item_path, {"item_id", "prompt"})
    require_unique(transcripts, "id", transcript_path)
    require_unique(items, "item_id", item_path)

    template = prompt_path.read_text(encoding="utf-8")
    instructions = instructions_path.read_text(encoding="utf-8")
    model = get_model()
    jobs = build_jobs(transcripts, items, template, instructions, model)

    print(f"Prepared {len(jobs)} ratings.")

    # Save the complete plan before making any API calls.
    write_jobs(jobs, RUN_DIR / "jobs.jsonl")
    write_manifest(
        jobs,
        model,
        {
            "transcripts": transcript_path,
            "items": item_path,
            "prompt": prompt_path,
            "instructions": instructions_path,
        },
        RUN_DIR / "manifest.json",
    )

    # One call at a time. Each result is saved before the next call starts.
    # Run this script again after an interruption; completed jobs are skipped.
    records = run_jobs(jobs, RUN_DIR / "raw_results.jsonl")
    rows = write_results(records, RUN_DIR / "results.csv")

    completed = sum(record["status"] == "completed" for record in records)
    failed = len(records) - completed
    parse_failed = sum(row["parse_status"] == "parse_failed" for row in rows)
    print(f"Completed {completed}/{len(jobs)} ratings.")
    if failed:
        print(f"API failures: {failed}. Run again to retry them.")
    if parse_failed:
        print(f"Parse failures: {parse_failed}. Inspect results.csv.")
    print(f"Results: {RUN_DIR / 'results.csv'}")
    return 1 if failed or parse_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
