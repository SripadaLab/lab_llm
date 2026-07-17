# Research Pilot Director

One goal. Five bounded tools. Real approval gates.

The agent inspects the demo study, estimates a three-transcript pilot, and
pauses before making the pilot requests. After approval, it validates the
saved results and pauses again before writing `review.html`.

`example.py` stays small. `pilot_tools.py` contains the bounded tools.
`study_helpers.py` contains this demo's study inspection and cost estimate.

```bash
./.bin/uv pip install -e ".[agents]"
./scripts/run.sh examples/14_research_agent/example.py
```

The agent run itself uses model calls. Approval gates protect the additional
pilot spend and file-writing tools. The complete run is visible in the OpenAI
Traces dashboard.

The Agents SDK is an optional dependency. The rest of `lab_llm` stays small.
