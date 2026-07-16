# Module 1: From ChatGPT to programmatic tools

The first programmatic call: send input from code, get a model response back.
This is the same example you ran live on the workshop site (Module 1, page 2),
using the OpenAI Python package directly.

## Two versions

These are the two tracks of the workshop side by side:

- `example.py`: **build it from scratch.** The raw call, exactly as shown on the
  site, using the OpenAI package directly.
- `nicer_example.py`: **adopt the package.** The same call through the `lab_llm`
  helper (`call_llm`), which loads your `.env`, uses `DEFAULT_MODEL`, keeps the
  full response, and fails closed if the response did not complete.

## Run

```bash
./scripts/run.sh examples/01_first_call/example.py           # macOS / Linux
.\scripts\run.ps1 examples\01_first_call\example.py          # Windows

./scripts/run.sh examples/01_first_call/nicer_example.py     # the helper version
```

## What to expect

A short reply printed to the terminal. The exact wording varies each run.
