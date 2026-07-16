# Workshop code: `lab_llm`

The take-home code for the **LLM APIs for Research Analysis** workshop.

The workshop [**site**](https://llm-workshop.cap-study.com/) does the live teaching. This repo is the polished result:
one small reusable package (`lab_llm`) plus a runnable example per module.

## Layout

```
lab_llm/                the reusable package (install once, use everywhere)
  calls.py              call_llm(), the reusable one-call helper
  conversations.py      stored and stateless multi-turn helpers
  jobs.py               sequential or multiprocess job execution
  records.py            durable responses and resume bookkeeping
  ratings.py            easy transcript x item rating batches
  runs.py               standard batch arguments, plans, and manifests
  inputs.py             prompt templates, transcripts, and item banks
  progress.py           elapsed time, ETA, and token-cost estimates
  structured.py         versioned output types and validation rules
  files.py              persistent or temporary Files API uploads
  tools.py              readable hosted-tool configurations
  config.py             API key + model, loaded from the environment
  errors.py             small package-specific exception types
examples/                runnable examples from the workshop
  01_first_call/        one call: raw SDK + lab_llm
  02_examples_gallery/  response-object field examples
  03_tiny_chat_loop/    multi-turn chat: raw SDK + lab_llm
  04_stateless_conversation/  local history; API response storage off
  05_files/              Files API upload and response input
  06_web/                hosted web-search example
  07_code_interpreter/   hosted Python example
  08_sequential_ratings/ transcript x item ratings; one or more workers
  09_check_results/      classify saved rating outcomes
  10_structured_outputs/ simple JSON Schema and typed output
  11_complex_structured_outputs/ nested evidence and justifications
  12_mood_diary_workflow/ extract, synthesize, score, audit, report
data/                   shared sample transcripts, item banks, and instructions
  mood_diaries/          eight synthetic, dated diary entries
  model_pricing.csv      saved OpenAI token-price snapshot for long runs
  synthetic_rating_results.jsonl  five example rating outcomes
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
./scripts/run.sh examples/01_first_call/example.py
```

**Windows (PowerShell)**

```powershell
.\scripts\setup.ps1         # installs a private Python + packages, all in this folder
# open .env and paste your OpenAI key
.\scripts\run.ps1 examples\01_first_call\example.py
```

Your key lives in `.env` (gitignored) and is read from the environment. It never
lives in code.

The helpers keep the complete OpenAI response. Reply text and token usage stay
easy to reach. `Conversation` uses one durable conversation ID.
`StatelessConversation` keeps the complete history locally and sends it again
with every turn. Both reuse their instructions across turns.

`PromptTemplate` validates named placeholders before a run. `TranscriptBank`
loads one text file per transcript. `ItemBank` loads uniquely identified items
and numeric bounds from CSV. Each stays iterable, so the transcript x item loop
remains ordinary Python.

`call_llm()` fails closed when a response is incomplete or failed. It raises
`LLMResponseError` with the full response attached. OpenAI SDK exceptions are
left unchanged, so callers can still catch specific authentication, rate-limit,
connection, and API errors.

`run_jobs()` runs independent calls sequentially by default. Set `workers` to
use multiple processes. Workers make API calls; the parent alone writes each
returned attempt to JSONL. Reusing the output path skips completed jobs and
retries failed ones. Pass explicit `TokenPricing` to add live elapsed time,
ETA, usage cost, and projected final cost. OpenAI responses contain token
counts, not a dollar charge; the saved rate card makes the estimate auditable.

`run_rating_batch()` is the short path for transcript x item studies. Define
the Pydantic result and list every study path. The helper supplies the standard
command line, preflight, resume, validation, CSV, and run summary. Use
`run_jobs()` directly when a study needs a different job shape.

Jobs may also carry an explicit Responses API `output_format`. The ratings
example uses strict Structured Outputs, validates item-specific ranges
again locally, supports a zero-call `--dry-run`, and saves `summary.json`.

`OutputContract` versions a Pydantic output type. It produces the Responses API
JSON Schema and parses JSON into that Python type. Pass it to `run_jobs()` to
validate each completed response before the parent process saves it. Parsed
output is saved as plain JSON. With the lower-level runner, research-specific
checks remain in the calling code.

Optional `.env` settings:

```dotenv
OPENAI_TIMEOUT=60       # seconds
OPENAI_MAX_RETRIES=2    # automatic retries after the first attempt
```

Leave either setting unset to use the OpenAI SDK default.

### Run a specific module

```bash
./scripts/run.sh examples/03_tiny_chat_loop/example.py      # macOS / Linux
.\scripts\run.ps1 examples\03_tiny_chat_loop\example.py     # Windows
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
python examples/01_first_call/example.py
```

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests use fake clients. They do not make paid API calls.

## Requirements

- No Python required. `setup` installs a private one. (Or use your own, 3.10+.)
- An OpenAI API key (`OPENAI_API_KEY`)
