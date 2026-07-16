"""Classify the latest saved result for every rating job.

Run:  ./scripts/run.sh examples/09_check_results/example.py \
        data/synthetic_rating_results.jsonl
"""
import argparse
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError


class Rating(BaseModel):
    """The structured output expected from each rating request."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    rating: float | None


def classify_rating(record):
    """Apply the five checks from the workshop walkthrough."""
    if record["status"] == "failed":
        return "failed", record["error"]["message"]

    if record["status"] == "validation_failed":
        return "validation_failed", record["error"]["message"]

    parsed = record.get("parsed_output")
    if parsed is None:
        # Older run files may contain output_text but no parsed_output.
        # Validate that saved JSON now. Still no API call.
        try:
            parsed = Rating.model_validate_json(record["output_text"])
        except ValidationError as error:
            first_error = error.errors()[0]
            field = ".".join(str(part) for part in first_error["loc"])
            return "validation_failed", f"{field}: {first_error['msg']}"
        parsed = parsed.model_dump(mode="json")

    rating = parsed["rating"]
    if rating is None:
        return "not_scored", None

    minimum = record["metadata"]["min_value"]
    maximum = record["metadata"]["max_value"]
    if not minimum <= rating <= maximum:
        return "parse_failed", rating

    return "parsed", rating


def load_latest_records(path):
    """Load the last saved attempt for each job ID."""
    latest = {}
    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                record = json.loads(line)
                latest[record["job_id"]] = record
    return latest.values()


def main():
    parser = argparse.ArgumentParser(
        description="Classify a ratings run's saved results.",
    )
    parser.add_argument("results", type=Path, help="Path to raw_results.jsonl")
    args = parser.parse_args()

    for record in load_latest_records(args.results):
        status, value = classify_rating(record)
        print(f"{record['job_id']:<42} {status:<19} {value}")


if __name__ == "__main__":
    main()
