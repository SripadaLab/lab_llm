# Mood diary workflow

One qualitative task. Five explicit stages.

```text
Mood diary files
        ↓
1. Extract candidate themes
        ↓
candidate_themes.jsonl
        ↓
2. Synthesize overlapping themes
        ↓
themes.json
        ├──────────────────────┐
        ↓                      ↓
3. Score + rank          4. Evidence audit
   deterministic code       selected themes only
        ↓                      ↓
theme_scores.csv       theme_evidence.jsonl
        └──────────┬───────────┘
                   ↓
5. Render report
                   ↓
              report.html
```

## Run

```bash
./scripts/run.sh examples/12_mood_diary_workflow/example.py
```

On Windows:

```powershell
.\scripts\run.ps1 examples\12_mood_diary_workflow\example.py
```

Eight extraction calls. One synthesis call. Three evidence-audit calls.
Twelve calls total. Re-running resumes completed model calls.

## Artifacts

- `candidate_themes.jsonl`: candidate themes, exact quotes, diary IDs.
- `themes.json`: overlapping candidates collapsed under stable theme IDs.
- `theme_scores.csv`: deterministic counts, salience, and rank.
- `theme_evidence.jsonl`: quote-grounded audits for the top three themes.
- `report.html`: scores and evidence joined for reading.

Raw API records stay under `_raw/`. They are not mixed with the clean research
artifacts.

The salience formula is a demonstration heuristic, not a validated measure: 70%
diary coverage + 30% mean extracted importance, computed in Python. The model
never counts or sorts.
