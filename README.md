# Workshop code — `lab_llm`

The take-home code for the **LLM APIs for Research Analysis** workshop.

The workshop **site** does the live teaching. This repo is the polished result:
one small reusable package (`lab_llm`) plus a runnable example per module.

## Layout

```
lab_llm/                the reusable package (install once, use everywhere)
  calls.py              call_llm() — the Module 1 helper
  config.py             API key + model, loaded from the environment
modules/                one folder per workshop module
  01_first_call/        example.py + README (+ expected output)
  02_ratings_at_scale/
  03_structured_outputs/
  04_multi_step_workflows/
  05_agentic_assistants/
  06_running_pipelines/
data/                   shared sample data (transcripts.csv, items.csv, …)
```

Each `modules/0N_*/example.py` imports from `lab_llm` — the core is written once,
and every module builds on the last. That is the reusable workflow, not six copies.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env      # then add your OpenAI key to .env
```

Your key is read from the environment (or `.env`, which is gitignored). It never
lives in code.

## Run a module

```bash
python modules/01_first_call/example.py
```

## Requirements

- Python 3.10+
- An OpenAI API key (`OPENAI_API_KEY`)
