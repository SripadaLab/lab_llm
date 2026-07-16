# Workshop code: `lab_llm`

The take-home code for the **LLM APIs for Research Analysis** workshop.

The workshop [**site**](https://llm-workshop.cap-study.com/) does the live teaching. This repo is the polished result:
one small reusable package (`lab_llm`) plus a runnable example per module.

## Layout

```
lab_llm/                the reusable package (install once, use everywhere)
  calls.py              call_llm(), the reusable one-call helper
  config.py             API key + model, loaded from the environment
  errors.py             small package-specific exception types
modules/                one folder per workshop module
  01_first_call/        example.py + README (+ expected output)
  02_ratings_at_scale/
  03_structured_outputs/
  04_multi_step_workflows/
  05_agentic_assistants/
  06_running_pipelines/
data/                   shared sample data (transcripts.csv, items.csv, …)
scripts/                setup / run / uninstall (macOS + Windows)
```

Module 1 uses the OpenAI package directly, the same first call you ran on the
site. From Module 2 on, each `modules/0N_*/example.py` imports from `lab_llm`.
The core is written once. Every module builds on the last.

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

The helper keeps the complete OpenAI response. Reply text and token usage stay
easy to reach.

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
./scripts/run.sh modules/02_ratings_at_scale/example.py     # macOS / Linux
.\scripts\run.ps1 modules\02_ratings_at_scale\example.py    # Windows
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
