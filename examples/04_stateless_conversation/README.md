# Module 1: Stateless conversation

A multi-turn conversation. History owned by your code.

No Conversation object. No `previous_response_id`. Every turn uses
`store=False`.

## Run

```bash
./scripts/run.sh examples/04_stateless_conversation/example.py       # macOS / Linux
.\scripts\run.ps1 examples\04_stateless_conversation\example.py      # Windows
```

Submit an empty prompt to stop.

## What carries the conversation?

`StatelessConversation` keeps a local `history` list. Each turn:

1. Add the new user message.
2. Send the complete history.
3. Keep every returned output item.

Reasoning and tool items too. Failed turns stay out of history.

## The tradeoff

Portable. No Conversations endpoint required. History disappears when the
process stops unless you save it.

Requests grow with every turn. Earlier context counts toward input tokens.

**Storage note.** `store=False` disables API response storage. Not a blanket
data-retention guarantee.

[OpenAI: manually manage conversation state](https://developers.openai.com/api/docs/guides/conversation-state#manually-manage-conversation-state)
