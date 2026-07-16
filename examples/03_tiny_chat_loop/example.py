"""Module 1 - the tiny chat loop from the workshop site.

Run:  ./scripts/run.sh examples/03_tiny_chat_loop/example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from dotenv import load_dotenv
load_dotenv()                              # load .env values into the environment

from openai import OpenAI                  # the OpenAI Python package

client = OpenAI()                          # reads OPENAI_API_KEY from the environment

conversation = client.conversations.create()      # one server-side conversation
instructions = "Be concise. Use plain language."  # directions for every turn

while True:                                # keep chatting
    prompt = input("You: ").strip()        # wait for your next message
    if not prompt:                         # blank message: stop
        break

    response = client.responses.create(    # send one turn
        model="gpt-5.4-mini",              # which model answers
        conversation=conversation.id,      # attach the shared conversation
        instructions=instructions,         # how the model should behave
        input=prompt,                      # your message
    )

    print("Model:", response.output_text)  # the reply, as text

client.conversations.delete(conversation.id)  # remove the server-side conversation
