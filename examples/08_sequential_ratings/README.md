# Sequential ratings

Rate every transcript on every item. Sequential or multiprocess.

The script keeps every study input visible: prompt, transcripts, items,
instructions, pricing, output folder, and response limit. `run_rating_batch()`
handles the repeatable run machinery.

## Inputs

- `data/transcripts/`: one plain-text file per transcript. The filename stem is
  its ID: `transcript_03.txt` becomes `transcript_03`.
- `data/items.csv`: item IDs, prompts, numeric ranges or exact text responses.
- `data/instructions.txt`: directions shared by every call.
- `prompt.txt`: where the item and transcript are placed.

`TranscriptBank` loads and validates the transcript folder. `ItemBank` does the
same for the item CSV. `PromptTemplate` allows only `{item}`,
`{response_requirements}`, and `{transcript}` here, then renders one prompt for
each pair. The runner builds `{response_requirements}` from each item's response
type, so categorical prompts do not contain numeric-range language.

For teaching purposes, this example shows four response styles:

- Numerical: set `min_value` and `max_value`, and leave
  `scoring_values` blank. Any number in the range is accepted.
- Likert: leave both bounds blank and list the scale labels, such as
  `Strongly disagree | Disagree | Neutral | Agree | Strongly agree`. The model
  returns one label exactly, ready for the researcher to map post-hoc.
- `likert_to_int`: set the bounds and write `scoring_values` as
  `0 = Not at all | 1 = Some | 2 = A lot`. The model returns `0`, `1`, or `2`.
- Categorical: leave both bounds blank and list exact acceptable responses,
  such as `Yes | No`. The model returns one of those strings exactly.

Do not mix numeric labels and text responses in one item.

Raw Likert and categorical items use the same safe mechanism: each request's
Structured Output schema contains an enum of that item's exact labels. This
prevents the model from returning a spelling or category outside the declared
set. `likert_to_int` requests use an integer enum for the mapped values.

Ten transcripts x four items = forty independent ratings.

For a quote-grounded variant, run the companion example:

```bash
./scripts/run.sh examples/08_sequential_ratings/example_with_citations.py \
  --run-name anxiety-with-citations-v1 \
  --workers 4
```

It defines nested citation models, requests exact transcript quotes, verifies
every returned quote locally against the transcript actually sent to the model,
and writes two additional exports:

- `ratings_with_citations.csv`: one row per transcript-item rating, with nested
  justifications and citations retained as JSON columns.
- `citations.csv`: one analysis-friendly row per quote, including its
  explanation and verification result.

Citation validation is grounding logic, not just schema validation. A response
with a correctly shaped but invented quote causes the example to exit nonzero.
When local de-identification is enabled, verification uses the filtered request
text because that is the version the model saw.

## Local de-identification

`example.py` exposes one switch for the entire batch:

```python
USE_LOCAL_DEIDENTIFICATION = True
```

When it is `True`, the example creates one local `Deidentifier`. The batch
runner gives each transcript its own placeholder scope: repeated identifiers
stay stable across every item for that transcript, while the next transcript
starts again at placeholders such as `[PRIVATE_PERSON_1]` and
`[PRIVATE_DATE_1]`. The runner filters the transcript before rendering each
prompt, so survey items, response choices, and shared instructions remain
unchanged. It then saves non-identifying audit counts with the result. Set the
switch to `False` only when sending the original text is appropriate for the
study and its approved data-handling policy.

The filter is lazy: `--dry-run` does not load its checkpoint or make an API
call. The source transcripts and `jobs.jsonl` remain local research artifacts
and may still contain the original text; protect the run directory accordingly.

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

The script displays every default path. The path flags are optional overrides.
Use them to run another study without editing the example.

- `manifest.json`: model, every source-file hash, and expected job count.
- `jobs.jsonl`: every exact request, saved before the first API call.
- `raw_results.jsonl`: complete responses. One saved attempt per line.
- `results.csv`: every rating and failure in one analysis-ready table.
- `summary.json`: job counts, parse rate, tokens, cost, runtime, and models.

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

Responses include token usage, not dollar cost. The script points to the
included `data/model_pricing.csv` snapshot. `--pricing-file` can override it.
The selected row is copied into `manifest.json`; the entire pricing file is
hashed with the other run inputs.

Check and refresh the table from its linked source before a real study,
especially after changing the model or service tier. These rates assume
standard processing. The estimate covers model tokens only.

The JSONL files include rendered prompts and transcript text. The entire
`runs/` folder is gitignored. Treat it as research data.

Run the script again after an interruption. Completed, validated job IDs are
skipped. API and Pydantic validation failures are tried again. Changed inputs,
prompts, or output contracts are rejected; start a new run folder for a changed
run.

The OpenAI SDK handles short request-level retries using `OPENAI_MAX_RETRIES`.
After a final failure, the runner saves the error and moves to the next job. It
does not retry that job again during the same pass. Running the script again
explicitly tries failed jobs again.

Each request uses one versioned Pydantic validation contract with a `rating`
field. To mix numeric and text items in one run, declare it as
`float | str | None`, as in `example.py`. The runner narrows the API schema for
each item: a number for numerical items, an exact string enum for raw Likert and
categorical items, and an exact integer enum for Likert-to-int items. It then
validates the returned JSON against the shared Pydantic contract before marking
the job complete. Local checks still enforce numeric bounds and exact declared
values. `null` means the transcript could not be scored. Invalid output is kept
as `raw_text` and marked `parse_failed`.
