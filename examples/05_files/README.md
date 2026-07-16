# Module 1: Files

Upload two local files through the Files API (a CSV of transcripts and a text
rubric). Reference both file IDs in one Responses request, so the model applies
the rubric to the data. Delete the server-side files when done.

## Run

```bash
./scripts/run.sh examples/05_files/example.py
./scripts/run.sh examples/05_files/nicer_example.py
```

`example.py` uses the OpenAI SDK directly. `nicer_example.py` uses `lab_llm`.
Its `with` block deletes the conversation and temporary files, even after an
error.
On Windows, use `.\scripts\run.ps1` and backslashes.

[OpenAI: file inputs](https://developers.openai.com/api/docs/guides/file-inputs)
