"""Module 1 - give one response access to web search.

Run:  ./scripts/run.sh examples/06_web/example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from dotenv import load_dotenv
load_dotenv()                              # load .env values into the environment

from openai import OpenAI                  # the OpenAI Python package

client = OpenAI()                          # reads OPENAI_API_KEY from the environment
conversation = client.conversations.create()  # one server-side conversation

response = client.responses.create(        # one web-enabled turn
    model="gpt-5.4-mini",                  # which model answers
    conversation=conversation.id,          # attach the shared conversation
    tools=[{"type": "web_search"}],        # available for this request
    input=(                                # the research request
        "Find the latest CDC guidance on sleep duration. "
        "Summarize it and cite the sources."
    ),
)

print(response.output_text)                # the answer, with citations
client.conversations.delete(conversation.id)  # remove the conversation
