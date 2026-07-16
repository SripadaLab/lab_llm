"""Structured output with the OpenAI SDK and a JSON Schema dictionary.

Run:  ./scripts/run.sh examples/10_structured_outputs/example.py
"""
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()                              # read OPENAI_API_KEY from your .env

from openai import OpenAI                  # the OpenAI Python package

client = OpenAI()                          # carries your key

minimum = 0
maximum = 4

template = Path("examples/10_structured_outputs/prompt.txt").read_text()
transcript = Path("data/transcripts/transcript_03.txt").read_text()
prompt = template.format(
    item="How much worry or anxiety does the speaker express?",
    min_value=minimum,
    max_value=maximum,
    transcript=transcript,
)

# The schema defines the exact JSON shape returned by the model.
rating_format = {
    "type": "json_schema",
    "name": "rating_v1",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "rating": {
                "anyOf": [
                    {"type": "number"},
                    {"type": "null"},
                ]
            }
        },
        "required": ["rating"],
        "additionalProperties": False,
    },
}

response = client.responses.create(        # request a schema-shaped reply
    model="gpt-5.4-mini",
    input=prompt,
    max_output_tokens=100,
    text={"format": rating_format},
)

output = json.loads(response.output_text)  # JSON text becomes a Python dict

# The schema checks shape. This research rule checks meaning.
rating = output["rating"]
if rating is not None and not minimum <= rating <= maximum:
    raise ValueError(f"rating must be between {minimum} and {maximum}")

print(output)
