"""Module 1 - let the model write and run Python.

Run:  ./scripts/run.sh examples/07_code_interpreter/example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from dotenv import load_dotenv
load_dotenv()                              # load .env values into the environment

from openai import OpenAI                  # the OpenAI Python package

client = OpenAI()                          # reads OPENAI_API_KEY from the environment
conversation = client.conversations.create()  # one server-side conversation

response = client.responses.create(        # one code-enabled turn
    model="gpt-5.4-mini",                  # which model answers
    conversation=conversation.id,          # attach the shared conversation
    tools=[{
        "type": "code_interpreter",       # allow hosted Python
        "container": {"type": "auto"},   # manage the sandbox for us
    }],
    input=(                                # the calculation request
        "Use Python to calculate the mean, median, and sample standard "
        "deviation of: 12, 15, 18, 22, 23."
    ),
)

print(response.output_text)                # the computed answer
client.conversations.delete(conversation.id)  # remove the conversation
