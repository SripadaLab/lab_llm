# Sequential ratings

Rate every transcript on every item, sequential or multiprocess.
`run_rating_batch()` handles the run machinery; the script keeps all study
inputs visible.

## Inputs

- `data/transcripts/`: one plain-text file per transcript. The filename stem is
  its ID: `transcript_03.txt` becomes `transcript_03`.
- `data/items.csv`: item IDs, prompts, numeric ranges or exact text responses.
- `data/instructions.txt`: directions shared by every call.
- `prompt.txt`: where the item and transcript are placed.

`PromptTemplate` allows only `{item}`, `{response_requirements}`, and
`{transcript}`. The runner builds `{response_requirements}` from each item's
response type, which is one of four styles:

- Numerical: set `min_value`/`max_value`, leave `scoring_values` blank.
- Likert: leave bounds blank, list labels
  (`Strongly disagree | Disagree | Neutral | Agree | Strongly agree`). The model
  returns one label exactly.
- `likert_to_int`: set bounds and write `scoring_values` as
  `0 = Not at all | 1 = Some | 2 = A lot`.
- Categorical: leave bounds blank, list exact responses (`Yes | No`).

Do not mix numeric and text labels in one item. Each request's schema is an enum
of that item's exact labels, so the model cannot return a value outside the set.

Ten transcripts x four items = forty independent ratings.

## Citations variant

```bash
./scripts/run.sh examples/08_sequential_ratings/example_with_citations.py \
  --run-name anxiety-with-citations-v1 \
  --workers 4
```

It requests exact transcript quotes and verifies each one locally against the
text actually sent to the model; a well-formed but invented quote exits nonzero.
It writes `ratings_with_citations.csv` (nested justifications and citations as
JSON columns) and `citations.csv` (one row per quote with its verification
result).

## Local de-identification

`example.py` has one switch:

```python
USE_LOCAL_DEIDENTIFICATION = True
```

When `True`, one `Deidentifier` gives each transcript its own placeholder scope:
repeated identifiers stay stable within a transcript, and the next transcript
restarts at `[PRIVATE_PERSON_1]`. Only transcripts are filtered; items and
instructions are unchanged, and non-identifying audit counts are saved with each
result. The filter is lazy, so `--dry-run` never loads it. Source transcripts
and `jobs.jsonl` may still contain original text; protect the run directory.

## Run

```bash
./scripts/run.sh examples/08_sequential_ratings/example.py \
  --run-name anxiety-structured-pilot \
  --transcripts studies/anxiety/transcripts \
  --items studies/anxiety/items.csv \
  --instructions studies/anxiety/instructions.txt \
  --pricing-file data/model_pricing.csv \
  --workers 4
```

On Windows:

```powershell
.\scripts\run.ps1 examples\08_sequential_ratings\example.py `
  --run-name anxiety-structured-pilot `
  --transcripts studies\anxiety\transcripts `
  --items studies\anxiety\items.csv `
  --instructions studies\anxiety\instructions.txt `
  --pricing-file data\model_pricing.csv `
  --workers 4
```

`--run-name` is required and creates `runs/<run-name>/`. Path flags are optional
overrides; the script prints every default. `--workers` defaults to `1`
(sequential, easiest to inspect); more workers can hit rate limits sooner. Only
the parent process writes the run files:

- `manifest.json`: model, every source-file hash, and expected job count.
- `jobs.jsonl`: every exact request, saved before the first API call.
- `raw_results.jsonl`: complete responses, one attempt per line.
- `results.csv`: every rating and failure in one analysis-ready table.
- `summary.json`: job counts, parse rate, tokens, cost, runtime, and models.

## Preflight and resume

`--dry-run` loads every input, renders every prompt, and prints the first job—no
API calls, no run directory. After each real request the runner prints elapsed
time, ETA, and an estimated final cost from actual token usage.

Responses report token usage, not dollars; cost comes from
`data/model_pricing.csv` (override with `--pricing-file`, refresh before a real
study). The selected row and a hash of the file go into `manifest.json`.

Re-running skips completed, validated jobs and retries failed ones. Changed
inputs, prompts, or contracts are rejected; start a new run folder for a changed
run. The `runs/` folder holds rendered prompts and transcript text—it is
gitignored; treat it as research data.
