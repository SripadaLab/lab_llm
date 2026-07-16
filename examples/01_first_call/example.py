"""Module 1 - your first programmatic call.

The same example you ran live on the workshop site (Module 1, page 2),
now on your own machine.

Run:  ./scripts/run.sh examples/01_first_call/example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from dotenv import load_dotenv
load_dotenv()                        # read OPENAI_API_KEY from your .env

from openai import OpenAI            # the OpenAI Python package

client = OpenAI()                    # carries your key

response = client.responses.create(  # ask the model for a reply
    model="gpt-5.4-mini",            # which model answers
    instructions="Be concise.",      # how it behaves
    input="Why is the sky blue?",    # your request
)

print(response.output_text)          # the reply, as text
