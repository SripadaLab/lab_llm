"""Generate a fresh ratings run. Then check every saved result.

Run:  ./scripts/run.sh examples/09_check_results/run_example.py
"""
import shutil
from pathlib import Path

from lab_llm import run_rating_batch

from example import Rating, classify_rating, load_latest_records


# This folder belongs only to this example. Safe to replace on every run.
RUN_NAME = "09-check-results-demo"
RUN_DIR = Path("runs") / RUN_NAME


def main():
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)

    result = run_rating_batch(
        Rating,
        prompt_path=Path("examples/08_sequential_ratings/prompt.txt"),
        transcripts_path=Path("data/transcripts"),
        items_path=Path("data/items.csv"),
        instructions_path=Path("data/instructions.txt"),
        pricing_path=Path("data/model_pricing.csv"),
        runs_path=Path("runs"),
        max_output_tokens=100,
        argv=["--run-name", RUN_NAME, "--workers", "1"],
    )

    print("\nSaved result checks:")
    records = load_latest_records(RUN_DIR / "raw_results.jsonl")
    for record in records:
        status, value = classify_rating(record)
        print(f"{record['job_id']:<42} {status:<19} {value}")

    return result


if __name__ == "__main__":
    raise SystemExit(main())
