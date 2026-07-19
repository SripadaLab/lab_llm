# Local de-identification before an LLM call

This example runs the open-weight OpenAI Privacy Filter on the researcher's
machine, assigns consistent typed placeholders, and previews every detected
span before anything is sent to an LLM.

The standard workshop setup installs the local filter. If your environment was
created before this example was added, update it once:

```bash
.bin/uv pip install --python .venv/bin/python -e ".[agents,privacy]"
```

Run the example:

```bash
./scripts/run.sh examples/15_local_deidentification/example.py
```

The first run downloads the checkpoint unless `OPF_CHECKPOINT` points at a
local copy. The script prints a local preview, then makes one API call. The
`deidentifier=privacy` argument ensures `call_llm()` sends the filtered copy,
not the original note.

For a raw SDK request with structured input, filter only the text-bearing
fields while preserving roles, item types, file IDs, and call IDs:

```python
from openai import OpenAI
from lab_llm import Deidentifier, deidentify_responses_input

privacy = Deidentifier(device="cpu")
safe = deidentify_responses_input(
    [{"role": "user", "content": "Interview with Maya Chen"}],
    deidentifier=privacy,
)
response = OpenAI().responses.create(
    model="gpt-5.4-mini",
    input=safe.value,
)
print(safe.summary.to_dict())
```

`preview()` shows original detected strings for local review only; use
`summary.to_dict()` in logs (counts and warnings, no identifiers).

This is a PII-masking layer, not proof of anonymization. Validate it against
representative study data and your approved privacy policy.
