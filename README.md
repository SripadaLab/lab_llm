# Workshop code: `lab_llm`

The take-home code for the **LLM APIs for Research Analysis** workshop.

The workshop [**site**](https://llm-workshop.cap-study.com/) does the live teaching. This repo is the polished result:
one small reusable package (`lab_llm`) plus a runnable example per module.

## Layout

```
lab_llm/                the reusable package (install once, use everywhere)
  calls.py              call_llm(), the reusable one-call helper
  conversations.py      stored and stateless multi-turn helpers
  files.py              upload and delete Files API objects
  tools.py              readable hosted-tool configurations
  config.py             API key + model, loaded from the environment
  errors.py             small package-specific exception types
modules/                runnable examples from the workshop
  01_first_call/        one call: raw SDK + lab_llm
  02_examples_gallery/  response-object field examples
  03_tiny_chat_loop/    multi-turn chat: raw SDK + lab_llm
  04_stateless_conversation/  local history; API response storage off
  05_files/              Files API upload and response input
  06_web/                hosted web-search example
  07_code_interpreter/   hosted Python example
data/                   shared sample data (transcripts.csv, items.csv, …)
scripts/                setup / run / uninstall (macOS + Windows)
```

Each module contains runnable examples. Files with `nicer_example` in the name
repeat the raw SDK calls through `lab_llm`. The core is written once. Later
examples build on it.

## Two ways to use this repo

- **Build it from scratch.** The workshop site and the raw `example.py` files
  use the plain OpenAI SDK, so you can see exactly what happens and write your
  own scripts.
- **Adopt the package.** `lab_llm` wraps those same calls with conveniences
  worth reusing: it loads your `.env`, fails closed on incomplete or failed
  responses (`LLMResponseError`), and honors optional timeout/retry settings.
  The `nicer_example.py` and gallery files show it in use.

Neither is more correct. Use the raw calls to learn; adopt `lab_llm` when you
would rather not rewrite the plumbing every time.

## Setup

You do **not** need Python installed. Setup downloads a private Python and all
dependencies **inside this folder**. Nothing is installed system-wide. Deleting
the folder removes the project files.

**macOS / Linux**

```bash
./scripts/setup.sh          # installs a private Python + packages, all in this folder
# open .env and paste your OpenAI key
./scripts/run.sh modules/01_first_call/example.py
```

**Windows (PowerShell)**

```powershell
.\scripts\setup.ps1         # installs a private Python + packages, all in this folder
# open .env and paste your OpenAI key
.\scripts\run.ps1 modules\01_first_call\example.py
```

Your key lives in `.env` (gitignored) and is read from the environment. It never
lives in code.

The helpers keep the complete OpenAI response. Reply text and token usage stay
easy to reach. `Conversation` uses one durable conversation ID.
`StatelessConversation` keeps the complete history locally and sends it again
with every turn. Both reuse their instructions across turns.

`call_llm()` fails closed when a response is incomplete or failed. It raises
`LLMResponseError` with the full response attached. OpenAI SDK exceptions are
left unchanged, so callers can still catch specific authentication, rate-limit,
connection, and API errors.

Optional `.env` settings:

```dotenv
OPENAI_TIMEOUT=60       # seconds
OPENAI_MAX_RETRIES=2    # automatic retries after the first attempt
```

Leave either setting unset to use the OpenAI SDK default.

### Run a specific module

```bash
./scripts/run.sh modules/03_tiny_chat_loop/example.py      # macOS / Linux
.\scripts\run.ps1 modules\03_tiny_chat_loop\example.py     # Windows
```

### Remove the local install

```bash
./scripts/uninstall.sh      # macOS / Linux
.\scripts\uninstall.ps1     # Windows
```

This deletes the private Python, the environment, caches, and `.env`. Source
code and run outputs stay. Deleting the whole folder removes those too.

### Prefer your own Python?

If you already have Python 3.10+ and would rather manage it yourself:

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env           # then add your OpenAI key
python modules/01_first_call/example.py
```

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests use fake clients. They do not make paid API calls.

## Requirements

- No Python required. `setup` installs a private one. (Or use your own, 3.10+.)
- An OpenAI API key (`OPENAI_API_KEY`)
