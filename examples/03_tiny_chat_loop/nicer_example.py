"""Module 1 - the tiny chat loop, using the lab_llm helper.

Run:  ./scripts/run.sh examples/03_tiny_chat_loop/nicer_example.py
"""
from lab_llm import Conversation       # the workshop's conversation helper

with Conversation(                     # create one conversation
    instructions="Be concise. Use plain language.",  # directions for every turn
) as chat:
    while True:                        # keep chatting
        prompt = input("You: ").strip()  # wait for your next message
        if not prompt:                 # blank message: stop
            break

        result = chat.send(prompt)      # send it in the same conversation
        print("Model:", result.text)    # the reply, as text

# Conversation deleted. Also runs after an error or Ctrl+C.
