"""Nested structured output with the OpenAI SDK and JSON Schema.

Run:  ./scripts/run.sh examples/11_complex_structured_outputs/example.py
"""
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()                              # read OPENAI_API_KEY from your .env

from openai import OpenAI                  # the OpenAI Python package

client = OpenAI()                          # carries your key

template = Path("examples/11_complex_structured_outputs/prompt.txt").read_text()
transcript = Path("data/transcripts/transcript_03.txt").read_text()
prompt = template.format(date="2026-07-01", transcript=transcript)

# Objects can contain lists of other schema-shaped objects.
assessment_format = {
    "type": "json_schema",
    "name": "anxiety_assessment_v1",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "rating": {"type": "number"},
            "justifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "explanation": {"type": "string"},
                        "quotes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "date": {"type": "string"},
                                },
                                "required": ["text", "date"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["explanation", "quotes"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["rating", "justifications"],
        "additionalProperties": False,
    },
}

response = client.responses.create(
    model="gpt-5.4-mini",
    input=prompt,
    max_output_tokens=800,
    text={"format": assessment_format},
)

assessment = json.loads(response.output_text)

if not 0 <= assessment["rating"] <= 100:
    raise ValueError("rating must be between 0 and 100")

print(json.dumps(assessment, indent=2))
