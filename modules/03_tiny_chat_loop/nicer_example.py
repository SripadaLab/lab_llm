"""Module 1 - the tiny chat loop, using the lab_llm helper.

Run:  ./scripts/run.sh modules/03_tiny_chat_loop/nicer_example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from lab_llm import Conversation       # the workshop's conversation helper

chat = Conversation(                   # create one conversation
    instructions="Be concise. Use plain language.",  # directions for every turn
)

while True:                            # keep chatting
    prompt = input("You: ").strip()    # wait for your next message
    if not prompt:                     # blank message: stop
        break

    result = chat.send(prompt)          # send it in the same conversation
    print("Model:", result.text)        # the reply, as text

chat.delete()                           # remove the server-side conversation
