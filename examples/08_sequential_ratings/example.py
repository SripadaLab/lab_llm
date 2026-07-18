"""Rate every transcript on every survey item.

Run:  ./scripts/run.sh examples/08_sequential_ratings/example.py \
        --run-name anxiety-pilot \
        --pricing-file data/model_pricing.csv \
        --workers 4
"""
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from lab_llm import Deidentifier, run_rating_batch


# One switch for the whole batch. Set to False only when sending the original
# text is appropriate for the study and its approved data-handling policy.
USE_LOCAL_DEIDENTIFICATION = True


class Rating(BaseModel):
    """The data we want back from each request."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    rating: float | str | None


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
            deidentifier=(
                Deidentifier(device="cpu")
                if USE_LOCAL_DEIDENTIFICATION
                else None
            ),
        )
    )
