# Module 1: Files

Upload a local file through the Files API. Reference its file ID in a Responses
request. Delete the server-side file when done.

## Run

```bash
./scripts/run.sh modules/05_files/example.py
./scripts/run.sh modules/05_files/nicer_example.py
```

`example.py` uses the OpenAI SDK directly. `nicer_example.py` uses `lab_llm`.
On Windows, use `.\scripts\run.ps1` and backslashes.

[OpenAI: file inputs](https://developers.openai.com/api/docs/guides/file-inputs)
