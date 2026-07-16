# Complex structured outputs

Return one assessment with nested justifications and dated quotes.

## Run

```bash
./scripts/run.sh examples/10_complex_structured_outputs/example.py
./scripts/run.sh examples/10_complex_structured_outputs/nicer_example.py
```

On Windows:

```powershell
.\scripts\run.ps1 examples\10_complex_structured_outputs\example.py
.\scripts\run.ps1 examples\10_complex_structured_outputs\nicer_example.py
```

## Two versions

`example.py` writes the complete nested JSON Schema by hand. Every object lists
its properties, required fields, and `additionalProperties` rule.

`nicer_example.py` expresses the same structure with three small Pydantic
models: `Quote`, `Justification`, and `Assessment`. Nested Python types produce
the nested API schema.

Both versions keep the 0–100 research rule visible after parsing. Schema shape
and research meaning remain separate checks.
