# Structured outputs

Request one rating in a known shape. Validate what its value means for the
research task.

## Run

```bash
./scripts/run.sh examples/09_structured_outputs/example.py
./scripts/run.sh examples/09_structured_outputs/nicer_example.py
```

On Windows:

```powershell
.\scripts\run.ps1 examples\09_structured_outputs\example.py
.\scripts\run.ps1 examples\09_structured_outputs\nicer_example.py
```

## Two versions

`example.py` uses the OpenAI SDK directly. The output format is an ordinary
JSON Schema dictionary. `json.loads()` turns the reply into a Python
dictionary.

`nicer_example.py` describes the same shape as a Pydantic model.
`OutputContract` supplies the API schema and parses the reply into a typed
Python object.

## Two checks

The JSON Schema checks structure:

- Is `rating` present?
- Is it a number or `null`?
- Are there unexpected fields?

The application rule checks meaning:

- Is a numeric rating inside this item's allowed range?

The range check stays ordinary Python in both versions. Correct shape does not
guarantee a valid research value.
