# Sequential ratings

Rate every transcript on every item. One call at a time.

## Inputs

- `data/transcripts/`: one plain-text file per transcript. The filename stem is
  its ID: `transcript_03.txt` becomes `transcript_03`.
- `data/items.csv`: item IDs and rating prompts.
- `data/instructions.txt`: directions shared by every call.
- `prompt.txt`: where the item and transcript are placed.

Ten transcripts x two items = twenty independent ratings.

## Run

```bash
./scripts/run.sh examples/08_sequential_ratings/example.py
```

On Windows:

```powershell
.\scripts\run.ps1 examples\08_sequential_ratings\example.py
```

Results go to `runs/08_sequential_ratings/`:

- `manifest.json`: model, every source-file hash, and expected job count.
- `jobs.jsonl`: every exact request, saved before the first API call.
- `raw_results.jsonl`: complete responses. One saved attempt per line.
- `results.csv`: every rating and failure in one analysis-ready table.

The JSONL files include rendered prompts and transcript text. The entire
`runs/` folder is gitignored. Treat it as research data.

Run the script again after an interruption. Completed job IDs are skipped.
Failed jobs are tried again. Changed inputs or prompts are rejected; start a
new run folder for a changed run.

The OpenAI SDK handles short request-level retries using `OPENAI_MAX_RETRIES`.
After a final failure, the runner saves the error and moves to the next job. It
does not retry that job again during the same pass. Running the script again
explicitly tries failed jobs again.

Ratings must be an exact number from 0 to 100, or `NA`. Invalid model output is
kept as `raw_text` and marked `parse_failed`; it is never guessed from a loose
text match.
