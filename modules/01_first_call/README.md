# Module 1: From ChatGPT to programmatic tools

The first programmatic call: send input from code, get a model response back.
This is the same example you ran live on the workshop site (Module 1, page 2),
using the OpenAI Python package directly.

## Two versions

- `example.py`: the raw call, exactly as shown on the site.
- `nicer_example.py`: the same call through the `lab_llm` helper (`call_llm`),
  which loads your `.env`, uses `DEFAULT_MODEL`, and keeps the full response.
  Text and token usage are ready to use.

## Run

```bash
./scripts/run.sh modules/01_first_call/example.py           # macOS / Linux
.\scripts\run.ps1 modules\01_first_call\example.py          # Windows

./scripts/run.sh modules/01_first_call/nicer_example.py     # the helper version
```

## What to expect

A short reply printed to the terminal. The exact wording varies each run.
