"""Rate every transcript on every survey item.

Run:  ./scripts/run.sh examples/08_sequential_ratings/example.py \
        --run-name anxiety-pilot \
        --pricing-file data/model_pricing.csv \
        --workers 4
"""
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from lab_llm import run_rating_batch


class Rating(BaseModel):
    """The data we want back from each request."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    rating: float | None


if __name__ == "__main__":
    raise SystemExit(
        run_rating_batch(
            Rating,
            prompt_path=Path("examples/08_sequential_ratings/prompt.txt"),
            transcripts_path=Path("data/transcripts"),
            items_path=Path("data/items.csv"),
            instructions_path=Path("data/instructions.txt"),
            pricing_path=Path("data/model_pricing.csv"),
            runs_path=Path("runs"),
            max_output_tokens=100,
        )
    )
