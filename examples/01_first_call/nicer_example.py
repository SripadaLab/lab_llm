"""Module 1 - the same first call, using the lab_llm helper.

Compare this with example.py. `call_llm()` wraps the OpenAI call, loads your
.env for you, uses DEFAULT_MODEL, and keeps the full response. Reply text,
model, and token usage stay easy to reach.

Run:  ./scripts/run.sh examples/01_first_call/nicer_example.py
"""
from lab_llm import call_llm      # the workshop's one-call helper

result = call_llm(
    "Why is the sky blue?",       # your request
    instructions="Be concise.",   # how the model should behave
    # model="gpt-5.4-mini",       # optional; defaults to DEFAULT_MODEL from .env
)

print(result.text)                # the reply, as text
print(result.usage)               # token counts, when the API reports them
