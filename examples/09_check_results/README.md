# Check saved results

Classify the latest saved result for every rating job.

## Generate and check a run

One command. A fresh ratings run. Then its five outcome checks:

```bash
./scripts/run.sh examples/09_check_results/run_example.py
```

On Windows:

```powershell
.\scripts\run.ps1 examples\09_check_results\run_example.py
```

Twenty API calls. Sequential. Replaces only
`runs/09-check-results-demo/` each time.

## Check the included JSONL

Run the synthetic JSONL. Five records. Five outcomes:

```bash
./scripts/run.sh examples/09_check_results/example.py \
  data/synthetic_rating_results.jsonl
```

On Windows:

```powershell
.\scripts\run.ps1 examples\09_check_results\example.py `
  data\synthetic_rating_results.jsonl
```

No API calls. Deterministic output.

## Check your run

Point the same script at a batch run:

```bash
./scripts/run.sh examples/09_check_results/example.py \
  runs/anxiety-structured-pilot/raw_results.jsonl
```

Each job becomes one of five outcomes: `failed`, `validation_failed`,
`parsed`, `not_scored`, or `parse_failed`. A JSONL file may contain retries.
Only the latest saved attempt for each job ID is checked.
