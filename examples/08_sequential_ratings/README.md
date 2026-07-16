# Sequential ratings

Rate every transcript on every item. Sequential or multiprocess.

## Inputs

- `data/transcripts/`: one plain-text file per transcript. The filename stem is
  its ID: `transcript_03.txt` becomes `transcript_03`.
- `data/items.csv`: item IDs, rating prompts, and allowed numeric ranges.
- `data/instructions.txt`: directions shared by every call.
- `prompt.txt`: where the item and transcript are placed.

`TranscriptBank` loads and validates the transcript folder. `ItemBank` does the
same for the item CSV. `PromptTemplate` allows only `{item}`, `{min_value}`,
`{max_value}`, and `{transcript}` here, then renders one prompt for each pair.

Ten transcripts x two items = twenty independent ratings.

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

`--run-name` is required. It creates `runs/<run-name>/`. For this example,
results go to `runs/anxiety-structured-pilot/`:

The three input-path options are optional. Without them, the example uses
`data/transcripts/`, `data/items.csv`, and `data/instructions.txt`.

- `manifest.json`: model, every source-file hash, and expected job count.
- `jobs.jsonl`: every exact request, saved before the first API call.
- `raw_results.jsonl`: complete responses. One saved attempt per line.
- `results.csv`: every rating and failure in one analysis-ready table.
- `summary.json`: job counts, parsing, tokens, cost, runtime, and models.

`--workers` defaults to `1`: sequential and easiest to inspect. A larger value
uses that many worker processes. Start small. More workers can hit provider
rate limits sooner. Only the parent process writes the run files.

## Preflight

Validate the entire run before spending anything:

```bash
./scripts/run.sh examples/08_sequential_ratings/example.py \
  --run-name anxiety-pilot \
  --transcripts studies/anxiety/transcripts \
  --items studies/anxiety/items.csv \
  --instructions studies/anxiety/instructions.txt \
  --pricing-file data/model_pricing.csv \
  --dry-run
```

This loads every input, renders every prompt, and prints the first job. No API
calls. No run directory.

After each request, the runner prints elapsed time, ETA, cost so far, and an
estimated final cost. The estimate uses actual token usage from completed jobs
for the jobs still pending. It becomes more useful as the run progresses.

Responses include token usage, not dollar cost. `--pricing-file` is required.
The included `data/model_pricing.csv` is a snapshot of OpenAI's published
standard token rates. The selected row is copied into `manifest.json`; the
entire pricing file is hashed with the other run inputs.

Check and refresh the table from its linked source before a real study,
especially after changing the model or service tier. These rates assume
standard processing. The estimate covers model tokens only.

The JSONL files include rendered prompts and transcript text. The entire
`runs/` folder is gitignored. Treat it as research data.

Run the script again after an interruption. Completed job IDs are skipped.
Failed jobs are tried again. Changed inputs or prompts are rejected; start a
new run folder for a changed run.

The OpenAI SDK handles short request-level retries using `OPENAI_MAX_RETRIES`.
After a final failure, the runner saves the error and moves to the next job. It
does not retry that job again during the same pass. Running the script again
explicitly tries failed jobs again.

Each request uses a strict JSON Schema with one `rating` field. A numeric value
must fall inside that item's `min_value` and `max_value`; `null` means the
transcript could not be scored. Application-side validation still checks every
returned value. Invalid output is kept as `raw_text` and marked `parse_failed`.
