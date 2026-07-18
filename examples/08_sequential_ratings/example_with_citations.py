"""Rate every transcript and retain locally verified supporting quotes.

Run:  ./scripts/run.sh examples/08_sequential_ratings/example_with_citations.py \
        --run-name anxiety-with-citations-v1 \
        --pricing-file data/model_pricing.csv \
        --workers 4
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from lab_llm import Deidentifier, run_rating_batch


USE_LOCAL_DEIDENTIFICATION = True
RUNS_PATH = Path("runs")
TRANSCRIPT_MARKER = "\nTranscript:\n"


class Citation(BaseModel):
    """One exact quote copied from the transcript sent to the model."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        description="An exact verbatim quote copied from the transcript."
    )


class Justification(BaseModel):
    """A brief interpretation with the transcript evidence supporting it."""

    model_config = ConfigDict(extra="forbid")

    explanation: str
    citations: list[Citation] = Field(
        min_length=1,
        max_length=1,
        description="Exactly one brief quote copied from the transcript.",
    )


class RatingWithCitations(BaseModel):
    """The item response plus nested, quote-grounded justifications."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    rating: float | str | None
    justifications: list[Justification] = Field(
        max_length=1,
        description=(
            "One quote-grounded justification for a scored response, or an "
            "empty list for a null response."
        ),
    )


def load_latest_records(path: Path) -> list[dict]:
    """Load the latest saved attempt for each job, preserving job order."""
    latest = {}
    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                record = json.loads(line)
                latest[record["job_id"]] = record
    return list(latest.values())


def audit_citations(record: dict) -> tuple[str, list[str], list[dict]]:
    """Verify quotes against the exact transcript text sent to the model."""
    if record.get("status") != "completed":
        return "not_run", [], []

    parsed = record.get("parsed_output")
    if not isinstance(parsed, dict):
        return "failed", ["completed record has no parsed output"], []

    try:
        transcript = _sent_transcript(record)
    except ValueError as exc:
        return "failed", [str(exc)], []

    rating = parsed.get("rating")
    justifications = parsed.get("justifications") or []
    errors = []
    citation_audits = []

    if rating is None and justifications:
        errors.append("a null rating must have no justifications")
    if rating is not None and not justifications:
        errors.append("a scored rating must have at least one justification")

    for justification_number, justification in enumerate(
        justifications,
        start=1,
    ):
        explanation = justification.get("explanation", "")
        citations = justification.get("citations") or []
        if not explanation.strip():
            errors.append(
                f"justification {justification_number} has no explanation"
            )
        if not citations:
            errors.append(
                f"justification {justification_number} has no citations"
            )

        for citation_number, citation in enumerate(citations, start=1):
            quote = citation.get("text", "")
            verified = bool(quote) and quote in transcript
            citation_audits.append({
                "justification_number": justification_number,
                "citation_number": citation_number,
                "explanation": explanation,
                "quote": quote,
                "quote_verified": verified,
            })
            if not verified:
                errors.append(
                    "citation "
                    f"{justification_number}.{citation_number} is not an "
                    "exact quote from the transcript sent to the model"
                )

    return ("failed" if errors else "passed"), errors, citation_audits


def write_citation_exports(records: list[dict], run_dir: Path) -> int:
    """Write job-level and citation-level CSVs; return failed audit count."""
    rating_rows = []
    citation_rows = []
    failed_audits = 0

    for record in records:
        parsed = record.get("parsed_output") or {}
        metadata = record.get("metadata") or {}
        status, errors, citation_audits = audit_citations(record)
        if status == "failed":
            failed_audits += 1

        justifications = parsed.get("justifications") or []
        citation_texts = [item["quote"] for item in citation_audits]
        rating_rows.append({
            "job_id": record["job_id"],
            "transcript_id": metadata.get("transcript_id"),
            "transcript_file": metadata.get("transcript_file"),
            "item_id": metadata.get("item_id"),
            "status": record.get("status"),
            "rating": parsed.get("rating"),
            "citation_validation": status,
            "validation_errors": json.dumps(errors, ensure_ascii=False),
            "justification_count": len(justifications),
            "citation_count": len(citation_audits),
            "justifications_json": json.dumps(
                justifications,
                ensure_ascii=False,
            ),
            "citations_json": json.dumps(
                citation_texts,
                ensure_ascii=False,
            ),
        })

        for citation in citation_audits:
            citation_rows.append({
                "job_id": record["job_id"],
                "transcript_id": metadata.get("transcript_id"),
                "transcript_file": metadata.get("transcript_file"),
                "item_id": metadata.get("item_id"),
                "rating": parsed.get("rating"),
                **citation,
            })

    _write_csv(
        run_dir / "ratings_with_citations.csv",
        rating_rows,
        (
            "job_id", "transcript_id", "transcript_file", "item_id",
            "status", "rating", "citation_validation",
            "validation_errors", "justification_count", "citation_count",
            "justifications_json", "citations_json",
        ),
    )
    _write_csv(
        run_dir / "citations.csv",
        citation_rows,
        (
            "job_id", "transcript_id", "transcript_file", "item_id",
            "rating", "justification_number", "citation_number",
            "explanation", "quote", "quote_verified",
        ),
    )
    return failed_audits


def _sent_transcript(record: dict) -> str:
    """Extract the transcript from the durable request, after filtering."""
    prompt = (record.get("request") or {}).get("input")
    if not isinstance(prompt, str):
        raise ValueError("record has no saved request input")
    _, marker, transcript = prompt.partition(TRANSCRIPT_MARKER)
    if not marker:
        raise ValueError("saved request does not contain a Transcript section")
    return transcript.rstrip()


def _write_csv(path: Path, rows: list[dict], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _options(argv: list[str]):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--dry-run", action="store_true")
    options, _ = parser.parse_known_args(argv)
    return options


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    privacy = (
        Deidentifier(device="cpu")
        if USE_LOCAL_DEIDENTIFICATION
        else None
    )
    exit_code = run_rating_batch(
        RatingWithCitations,
        prompt_path=Path(
            "examples/08_sequential_ratings/prompt_with_citations.txt"
        ),
        transcripts_path=Path("data/transcripts"),
        items_path=Path("data/items.csv"),
        instructions_path=Path("data/instructions.txt"),
        pricing_path=Path("data/model_pricing.csv"),
        runs_path=RUNS_PATH,
        max_output_tokens=800,
        deidentifier=privacy,
        argv=argv,
    )

    options = _options(argv)
    if options.dry_run:
        return exit_code

    run_dir = RUNS_PATH / options.run_name
    records = load_latest_records(run_dir / "raw_results.jsonl")
    failed_audits = write_citation_exports(records, run_dir)
    print(f"Citation ratings: {run_dir / 'ratings_with_citations.csv'}")
    print(f"Citation rows: {run_dir / 'citations.csv'}")
    if failed_audits:
        print(
            f"Citation validation failures: {failed_audits}. "
            "Inspect ratings_with_citations.csv."
        )
    return 1 if exit_code or failed_audits else 0


if __name__ == "__main__":
    raise SystemExit(main())
