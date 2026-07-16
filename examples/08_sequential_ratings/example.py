"""Sequential ratings: rate every transcript on every item, one call at a time.

Run:  ./scripts/run.sh examples/08_sequential_ratings/example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lab_llm import LLMJob, run_jobs


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


def require_unique(rows, column, path):
    """Catch duplicate IDs before they can overwrite or skip a rating."""
    values = [row[column] for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"{path} contains duplicate {column} values")


def build_jobs(transcripts, items, template, instructions):
    """Create the transcript x item grid."""
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
                max_output_tokens=100,       # guard against a runaway reply
                metadata={
                    "transcript_id": transcript_id,
                    "item_id": item_id,
                },
            ))
    return jobs


def parse_rating(text):
    """Parse only an exact number from 0 to 100, or the exact text NA."""
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
        "item_id",
        "model",
        "rating",
        "parse_status",
        "parse_error",
        "raw_text",
        "response_id",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for record in records:
            rating, parse_status, parse_error = parse_rating(
                record["output_text"]
            )
            usage = record.get("usage") or {}
            metadata = record["metadata"]
            writer.writerow({
                "job_id": record["job_id"],
                "transcript_id": metadata["transcript_id"],
                "item_id": metadata["item_id"],
                "model": record["model"],
                "rating": rating,
                "parse_status": parse_status,
                "parse_error": parse_error,
                "raw_text": record["output_text"],
                "response_id": record["response_id"],
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
            })


def main():
    """Load inputs, run every rating, then write the tidy CSV."""
    # Inputs stay separate: transcript table, item bank, and prompt template.
    transcript_path = DATA_DIR / "transcripts.csv"
    item_path = DATA_DIR / "items.csv"
    transcripts = read_table(transcript_path, {"id", "text"})
    items = read_table(item_path, {"item_id", "prompt"})
    require_unique(transcripts, "id", transcript_path)
    require_unique(items, "item_id", item_path)

    template = (MODULE_DIR / "prompt.txt").read_text(encoding="utf-8")
    instructions = (DATA_DIR / "instructions.txt").read_text(encoding="utf-8")
    jobs = build_jobs(transcripts, items, template, instructions)

    print(f"Prepared {len(jobs)} ratings.")

    # One call at a time. Each result is saved before the next call starts.
    # Run this script again after an interruption; completed jobs are skipped.
    records = run_jobs(jobs, RUN_DIR / "raw_results.jsonl")
    write_results(records, RUN_DIR / "results.csv")

    completed = sum(record["status"] == "completed" for record in records)
    print(f"Completed {completed}/{len(jobs)} ratings.")
    print(f"Results: {RUN_DIR / 'results.csv'}")


if __name__ == "__main__":
    main()
