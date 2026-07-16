"""Module 1 - the same web-search call, using lab_llm.

Run:  ./scripts/run.sh examples/06_web/nicer_example.py
"""
from lab_llm import Conversation, web_search_tool  # conversation + tool config

with Conversation() as chat:                # one server-side conversation
    result = chat.send(                     # one web-enabled turn
        "Find the latest CDC guidance on sleep duration. "
        "Summarize it and cite the sources.",
        tools=[web_search_tool()],          # available for this request
    )

    print(result.text)                      # the answer, with citations

# Conversation deleted. Also runs after an error or Ctrl+C.
