"""Module 1 — your first programmatic call.

Run:  python modules/01_first_call/example.py
Needs OPENAI_API_KEY in your environment (see the root README).
"""
from lab_llm import call_llm

result = call_llm(
    prompt=(
        "Summarize this abstract in two sentences: "
        "Daily mood variability was linked to sleep timing across six weeks. "
        "Effects were strongest in participants with irregular schedules."
    ),
    instructions="You are a careful research assistant. Avoid hype.",
    max_output_tokens=200,
)

print(result.text)
print(result.usage)
