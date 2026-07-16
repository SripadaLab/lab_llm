"""The same structured rating, using lab_llm and a Pydantic type.

Run:  ./scripts/run.sh examples/09_structured_outputs/nicer_example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from lab_llm import OutputContract, PromptTemplate, call_llm


class Rating(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    rating: float | None


minimum = 0
maximum = 4

contract = OutputContract("rating", "1", Rating)
template = PromptTemplate.from_file(
    "examples/09_structured_outputs/prompt.txt",
    fields=("item", "min_value", "max_value", "transcript"),
)
prompt = template.render(
    item="How much worry or anxiety does the speaker express?",
    min_value=str(minimum),
    max_value=str(maximum),
    transcript=Path("data/transcripts/transcript_03.txt").read_text(),
)

result = call_llm(
    prompt,
    output_format=contract.output_format,
    max_output_tokens=100,
)
rating = contract.parse(result.text)        # JSON becomes a typed Rating

if rating.rating is not None and not minimum <= rating.rating <= maximum:
    raise ValueError(f"rating must be between {minimum} and {maximum}")

print(rating)
