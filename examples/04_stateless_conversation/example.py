"""Module 1 - a stateless conversation.

No conversation ID. No previous_response_id. API response storage off.
This process keeps the history and sends it again with every turn.

Run:  ./scripts/run.sh examples/04_stateless_conversation/example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from lab_llm import StatelessConversation  # local conversation history

chat = StatelessConversation(
    instructions="Be concise. Use plain language.",  # directions for every turn
)

while True:                            # keep chatting
    prompt = input("You: ").strip()    # wait for your next message
    if not prompt:                     # blank message: stop
        break

    result = chat.send(prompt)          # resend the full history, plus this turn
    print("Model:", result.text)       # the reply, as text
