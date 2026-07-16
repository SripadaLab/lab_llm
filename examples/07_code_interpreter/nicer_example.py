"""Module 1 - the same Code Interpreter call, using lab_llm.

Run:  ./scripts/run.sh examples/07_code_interpreter/nicer_example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from lab_llm import Conversation, code_interpreter_tool  # conversation + tool config

with Conversation() as chat:                # one server-side conversation
    result = chat.send(                     # one code-enabled turn
        "Use Python to calculate the mean, median, and sample standard "
        "deviation of: 12, 15, 18, 22, 23.",
        tools=[code_interpreter_tool()],    # hosted Python, auto container
    )

    print(result.text)                      # the computed answer

# Conversation deleted. Also runs after an error or Ctrl+C.
