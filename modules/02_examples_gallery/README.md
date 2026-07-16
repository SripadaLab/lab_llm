# Module 1: Examples Gallery

Ten small prompts, and the response-object fields each one brings to life.
This mirrors the workshop site (Module 1, page 5), but here you run them for
real against your own key.

The site shows these calls **from scratch** with the raw OpenAI SDK. Here they
run through `lab_llm` (the **adopt the package** track), so the `cutoff` example
simply catches the `LLMResponseError` that `call_llm` raises when a response
does not complete.

## The examples

| Name        | Point                                               |
|-------------|-----------------------------------------------------|
| `simple`    | The baseline: `output_text`, `model`, `status`.     |
| `reasoning` | A `reasoning` item and `reasoning_tokens`; the steps stay private. |
| `tokens`    | `usage`: input, output, and total tokens.           |
| `cutoff`    | `status: incomplete` and `incomplete_details`.      |
| `refusal`   | `status: completed`, yet the text declines.         |
| `format`    | The `instructions` come back with the response.     |
| `structure` | The long path vs the `output_text` shortcut.        |
| `identity`  | `id`, `created_at`, `completed_at`.                  |
| `bad_model` | A bad model name raises `BadRequestError`.          |
| `bad_setting` | An out-of-range setting is rejected before the call. |

## Run

```bash
# every example
./scripts/run.sh modules/02_examples_gallery/examples_gallery.py          # macOS / Linux
.\scripts\run.ps1 modules\02_examples_gallery\examples_gallery.py         # Windows

# just one
./scripts/run.sh modules/02_examples_gallery/examples_gallery.py cutoff
```

## What to expect

Exact output varies. The fields explored here remain the same.

The `reasoning` example needs a parameter (`reasoning={"effort": "medium"}`)
that the `call_llm` helper does not wrap, so it drops down to the raw client.
That is the escape hatch whenever the helper is too small for what you need.
