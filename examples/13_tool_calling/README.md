# Tool calling

The model cannot open the study folder directly. It can request one bounded
function: `inspect_study()`.

The function runs locally. Its returned JSON is sent back to the model. The
full files are not sent, but every returned value becomes model input.

```bash
./scripts/run.sh examples/13_tool_calling/example.py
```
