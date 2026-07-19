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
  privacy.py            local PII detection + stable pseudonyms
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
  13_tool_calling/       raw Responses API function-tool loop
  14_research_agent/     multi-turn study investigator + hosted Python
  15_local_deidentification/ preview and locally filter research text
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

`call_llm()` fails closed on an incomplete or failed response, raising
`LLMResponseError` with the full response attached; OpenAI SDK exceptions pass
through unchanged. `run_jobs()` runs calls sequentially or across `workers`
processes, and only the parent writes results, so reusing the output path skips
completed jobs and retries failed ones. `run_rating_batch()` wraps the standard
command line, preflight, resume, validation, and CSV/summary output for
transcript x item studies. See the examples for the rest.

## Optional local de-identification

OpenAI Privacy Filter is an optional, open-weight model that runs before an API
request: unfiltered text stays on your machine and only the filtered copy is
sent. The standard setup installs it. If your environment predates local
de-identification, update it once:

```bash
.bin/uv pip install --python .venv/bin/python -e ".[agents,privacy]"
```

The first use downloads the checkpoint to `~/.opf/privacy_filter`. For an
offline environment, download and approve it first, set `OPF_CHECKPOINT` to that
directory, then disable network access. CPU is the default; pass `device="cuda"`
on a supported GPU. The checkpoint lives outside this project, so uninstall does
not remove it.

Reuse one `Deidentifier` across related text so the same person receives the
same process-local placeholder:

```python
from lab_llm import Deidentifier, call_llm

privacy = Deidentifier(device="cpu")
preview = privacy.deidentify("Interview with Maya Chen on 2026-04-12.")
print(preview.preview())                 # local review; reveals detected PII

result = call_llm(
    "Interview with Maya Chen on 2026-04-12.",
    instructions="Summarize the interview.",
    deidentifier=privacy,
)
print(result.deidentification.to_dict()) # counts only; no original PII
```

The same `deidentifier=` option works with `Conversation`,
`StatelessConversation`, `run_jobs`, `run_rating_batch`, `upload_file`, and
`temporary_file`. Use `deidentify_records()` for CSV/JSON columns and
`deidentify_responses_input()` for raw SDK message lists. Filtering only covers
UTF-8 text: extract text from binary formats first, and an already-uploaded file
ID cannot be protected retroactively.

Privacy Filter reduces exposure; it does not prove anonymity or compliance.
Evaluate it on representative in-domain data and document which labels you
filter. The default covers all eight released label categories.

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

This deletes the private Python, the environment (including the Privacy Filter
runtime), caches, and `.env`. Source code and run outputs stay. Privacy Filter
checkpoints outside the project are left in place.

### Prefer your own Python?

If you already have Python 3.10+ and would rather manage it yourself:

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[agents,privacy]"
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
