# Module 1: Tiny chat loop

A real multi-turn conversation. The same loop shown on Module 1, page 6.

## Two versions

- `example.py`: **build it from scratch.** The site code, using the OpenAI SDK
  directly.
- `nicer_example.py`: **adopt the package.** The same loop through
  `lab_llm.Conversation`.

The helper loads `.env`, uses `DEFAULT_MODEL`, keeps the full response, repeats
the instructions on every turn, and fails closed if a response does not
complete.

## Run

```bash
./scripts/run.sh examples/03_tiny_chat_loop/example.py          # macOS / Linux
.\scripts\run.ps1 examples\03_tiny_chat_loop\example.py         # Windows

./scripts/run.sh examples/03_tiny_chat_loop/nicer_example.py    # helper version
.\scripts\run.ps1 examples\03_tiny_chat_loop\nicer_example.py
```

Submit an empty prompt to stop.

## Try this

```text
You: Give a one-word name for a sleep-and-memory study.
Model: Noctis
You: Make it sound more serious.
Model: Somnolence
You: Now shorten it.
Model: Somno
```

The exact replies vary.

## What carries the conversation?

Both versions create one Conversation object. Every call passes its ID. OpenAI
stores each turn on that object, so the next call receives the earlier context.
Your script sends only the new prompt.

Each prompt makes a real API call. Earlier context still counts toward the
model's input tokens.

**Endpoint support.** Requires `/v1/conversations`. Not every compatible
endpoint supports it.

[OpenAI: conversation state](https://developers.openai.com/api/docs/guides/conversation-state#using-the-conversations-api)
