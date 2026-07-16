"""The same nested assessment, using lab_llm and Pydantic types.

Run:  ./scripts/run.sh examples/11_complex_structured_outputs/nicer_example.py
"""
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from lab_llm import OutputContract, PromptTemplate, call_llm


class Quote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    date: str


class Justification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str
    quotes: list[Quote]


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: float
    justifications: list[Justification]


contract = OutputContract("anxiety_assessment", "1", Assessment)
template = PromptTemplate.from_file(
    "examples/11_complex_structured_outputs/prompt.txt",
    fields=("date", "transcript"),
)
prompt = template.render(
    date="2026-07-01",
    transcript=Path("data/transcripts/transcript_03.txt").read_text(),
)

result = call_llm(
    prompt,
    output_format=contract.output_format,
    max_output_tokens=800,
)
assessment = contract.parse(result.text)

if not 0 <= assessment.rating <= 100:
    raise ValueError("rating must be between 0 and 100")

print(assessment.model_dump_json(indent=2))
