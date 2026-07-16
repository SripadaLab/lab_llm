"""Turn mood diaries into an inspectable, quote-grounded theme report.

Run:  ./scripts/run.sh examples/12_mood_diary_workflow/example.py
"""
from pathlib import Path

from report import render_report
from workflow import (
    audit_themes,
    extract_candidate_themes,
    load_diaries,
    score_themes,
    synthesize_themes,
)


DIARIES_PATH = Path("data/mood_diaries")
PROMPTS_PATH = Path("examples/12_mood_diary_workflow/prompts")
RUN_PATH = Path("runs/mood-diary-demo")


def main():
    diaries = load_diaries(DIARIES_PATH)

    candidates = extract_candidate_themes(
        diaries, PROMPTS_PATH, RUN_PATH, workers=4,
    )
    themes = synthesize_themes(candidates, PROMPTS_PATH, RUN_PATH)
    scores = score_themes(themes, candidates, len(diaries), RUN_PATH)
    evidence = audit_themes(
        themes, scores, candidates, diaries, PROMPTS_PATH, RUN_PATH,
    )
    render_report(themes, scores, evidence, RUN_PATH / "report.html")

    print("\nWorkflow complete.")
    for name in (
        "candidate_themes.jsonl", "themes.json", "theme_scores.csv",
        "theme_evidence.jsonl", "report.html",
    ):
        print(RUN_PATH / name)


if __name__ == "__main__":
    main()
