# Sequential ratings

Rate every transcript on every item. One call at a time.

## Inputs

- `data/transcripts.csv`: transcript IDs and text.
- `data/items.csv`: item IDs and rating prompts.
- `data/instructions.txt`: directions shared by every call.
- `prompt.txt`: where the item and transcript are placed.

Three transcripts x two items = six independent ratings.

## Run

```bash
./scripts/run.sh examples/08_sequential_ratings/example.py
```

On Windows:

```powershell
.\scripts\run.ps1 examples\08_sequential_ratings\example.py
```

Results go to `runs/08_sequential_ratings/`:

- `raw_results.jsonl`: complete responses. One saved attempt per line.
- `results.csv`: one analysis-ready row per transcript x item rating.

`raw_results.jsonl` includes the rendered prompts and transcript text. The
entire `runs/` folder is gitignored. Treat it as research data.

Run the script again after an interruption. Completed job IDs are skipped.
Failed jobs are tried again. A changed prompt under an existing job ID is
rejected; start a new run folder for changed inputs.

The OpenAI SDK handles short request-level retries using `OPENAI_MAX_RETRIES`.
The runner does not loop forever. After a final failure, it saves the error and
stops. Running the script again explicitly tries that failed job again.
