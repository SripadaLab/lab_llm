# Module 1: Code Interpreter

Give one Responses request access to hosted Python. Code runs in an isolated
container, not on your machine.

## Run

```bash
./scripts/run.sh modules/07_code_interpreter/example.py
./scripts/run.sh modules/07_code_interpreter/nicer_example.py
```

`example.py` uses the OpenAI SDK directly. `nicer_example.py` uses `lab_llm`.
On Windows, use `.\scripts\run.ps1` and backslashes.

[OpenAI: Code Interpreter](https://developers.openai.com/api/docs/guides/tools-code-interpreter)
