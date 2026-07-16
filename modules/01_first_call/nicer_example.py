"""Module 1 - the same first call, using the lab_llm helper.

Compare this with example.py. `call_llm()` wraps the OpenAI call, loads your
.env for you, uses DEFAULT_MODEL, and returns a tidy result: the reply text
plus the model and token usage.

Run:  ./scripts/run.sh modules/01_first_call/nicer_example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from lab_llm import call_llm      # the workshop's one-call helper

result = call_llm(
    "Why is the sky blue?",       # your request
    instructions="Be concise.",   # how the model should behave
)

print(result.text)                # the reply, as text
print(result.usage)               # token counts, when the API reports them
