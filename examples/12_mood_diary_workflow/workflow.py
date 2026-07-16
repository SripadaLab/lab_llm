"""Readable stages for the mood-diary workflow example."""

import csv
import json
from pathlib import Path

from lab_llm import LLMJob, OutputContract, PromptTemplate, run_jobs

from schemas import DiaryExtraction, ThemeAudit, ThemeSynthesis


INSTRUCTIONS = (
    "You are a careful qualitative research assistant. "
    "Use only the supplied material. Never invent quotes."
)


def load_diaries(directory: Path) -> list[dict]:
    """Load one dated diary entry per text file."""
    diaries = []
    for path in sorted(directory.glob("*.txt")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"{path} is empty")
        diaries.append({"diary_id": path.stem, "date": path.stem, "text": text})
    if not diaries:
        raise ValueError(f"{directory} contains no diary files")
    return diaries


def extract_candidate_themes(diaries, prompts_path, run_path, workers=1):
    """Stage 1: one structured extraction request per diary."""
    diary_by_id = {item["diary_id"]: item for item in diaries}
    template = PromptTemplate.from_file(
        prompts_path / "extract.txt",
        fields=("diary_id", "date", "diary"),
    )
    contract = OutputContract("diary_themes", "1", DiaryExtraction)
    jobs = [
        LLMJob(
            job_id=f"extract-{diary['diary_id']}",
            prompt=template.render(
                diary_id=diary["diary_id"],
                date=diary["date"],
                diary=diary["text"],
            ),
            instructions=INSTRUCTIONS,
            max_output_tokens=700,
            output_format=contract.output_format,
            metadata={"diary_id": diary["diary_id"], "date": diary["date"]},
        )
        for diary in diaries
    ]
    records = run_jobs(
        jobs,
        run_path / "_raw/01_extraction_requests.jsonl",
        workers=workers,
        output_contract=contract,
    )

    candidates = []
    for record in records:
        parsed = _parsed(record, "theme extraction")
        for number, theme in enumerate(parsed["themes"], start=1):
            diary = diary_by_id[record["metadata"]["diary_id"]]
            if theme["quote"] not in diary["text"]:
                raise ValueError(
                    f"extracted quote not found in {diary['diary_id']}: "
                    f"{theme['quote']!r}"
                )
            candidates.append({
                "candidate_id": f"{record['metadata']['diary_id']}-c{number:02d}",
                "diary_id": record["metadata"]["diary_id"],
                "date": record["metadata"]["date"],
                **theme,
            })
    _write_jsonl(run_path / "candidate_themes.jsonl", candidates)
    return candidates


def synthesize_themes(candidates, prompts_path, run_path):
    """Stage 2: collapse candidate themes while retaining their IDs."""
    if not candidates:
        raise ValueError("no candidate themes to synthesize")

    template = PromptTemplate.from_file(
        prompts_path / "synthesize.txt",
        fields=("candidates",),
    )
    contract = OutputContract("theme_synthesis", "1", ThemeSynthesis)
    job = LLMJob(
        job_id="synthesize-themes",
        prompt=template.render(candidates=json.dumps(candidates, indent=2)),
        instructions=INSTRUCTIONS,
        max_output_tokens=1600,
        output_format=contract.output_format,
    )
    record = run_jobs(
        [job],
        run_path / "_raw/02_synthesis_request.jsonl",
        output_contract=contract,
    )[0]
    parsed = _parsed(record, "theme synthesis")

    themes = [
        {"theme_id": f"theme_{number:02d}", **theme}
        for number, theme in enumerate(parsed["themes"], start=1)
    ]
    _check_membership(candidates, themes)
    _write_json(run_path / "themes.json", themes)
    return themes


def score_themes(themes, candidates, diary_count, run_path):
    """Stage 3: deterministic counts, salience scores, and ranks."""
    if not themes:
        raise ValueError("no themes to score")

    candidate_by_id = {item["candidate_id"]: item for item in candidates}
    rows = []
    for theme in themes:
        members = [candidate_by_id[item] for item in theme["candidate_ids"]]
        days = len({item["diary_id"] for item in members})
        mean_importance = sum(item["importance"] for item in members) / len(members)

        # Transparent demo heuristic. Not a validated research measure.
        coverage = 100 * days / diary_count
        salience = round(0.7 * coverage + 0.3 * (mean_importance / 5 * 100), 1)
        rows.append({
            "theme_id": theme["theme_id"],
            "diary_count": days,
            "candidate_count": len(members),
            "mean_importance": round(mean_importance, 2),
            "salience": salience,
        })

    rows.sort(key=lambda row: (-row["salience"], row["theme_id"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    _write_csv(run_path / "theme_scores.csv", rows)
    return rows


def audit_themes(themes, scores, candidates, diaries, prompts_path, run_path):
    """Stage 4: audit the three highest-ranked themes with exact quotes."""
    theme_by_id = {item["theme_id"]: item for item in themes}
    candidate_by_id = {item["candidate_id"]: item for item in candidates}
    diary_by_id = {item["diary_id"]: item for item in diaries}
    selected_ids = [item["theme_id"] for item in scores[:3]]
    template = PromptTemplate.from_file(
        prompts_path / "audit.txt",
        fields=("theme", "diaries"),
    )
    contract = OutputContract("theme_audit", "1", ThemeAudit)
    jobs = []

    for theme_id in selected_ids:
        theme = theme_by_id[theme_id]
        diary_ids = sorted({
            candidate_by_id[item]["diary_id"]
            for item in theme["candidate_ids"]
        })
        relevant_diaries = [diary_by_id[item] for item in diary_ids]
        jobs.append(LLMJob(
            job_id=f"audit-{theme_id}",
            prompt=template.render(
                theme=json.dumps(theme, indent=2),
                diaries=json.dumps(relevant_diaries, indent=2),
            ),
            instructions=INSTRUCTIONS,
            max_output_tokens=1000,
            output_format=contract.output_format,
            metadata={"theme_id": theme_id},
        ))

    records = run_jobs(
        jobs,
        run_path / "_raw/04_audit_requests.jsonl",
        output_contract=contract,
    )
    audits = []
    for record in records:
        audit = _parsed(record, "evidence audit")
        _verify_quotes(audit["quotes"], diary_by_id)
        audits.append({"theme_id": record["metadata"]["theme_id"], **audit})
    _write_jsonl(run_path / "theme_evidence.jsonl", audits)
    return audits


def _parsed(record, stage):
    if record["status"] != "completed":
        message = (record.get("error") or {}).get("message", "unknown error")
        raise RuntimeError(f"{stage} failed for {record['job_id']}: {message}")
    return record["parsed_output"]


def _check_membership(candidates, themes):
    expected = {item["candidate_id"] for item in candidates}
    if any(not theme["candidate_ids"] for theme in themes):
        raise ValueError("every theme must contain at least one candidate ID")
    assigned = [item for theme in themes for item in theme["candidate_ids"]]
    if len(assigned) != len(set(assigned)):
        raise ValueError("a candidate theme was assigned more than once")
    missing = expected - set(assigned)
    extra = set(assigned) - expected
    if missing or extra:
        raise ValueError(f"theme membership mismatch; missing={sorted(missing)}, extra={sorted(extra)}")


def _verify_quotes(quotes, diary_by_id):
    for quote in quotes:
        diary = diary_by_id.get(quote["diary_id"])
        if diary is None or quote["date"] != diary["date"]:
            raise ValueError(f"unknown diary reference: {quote['diary_id']}")
        if quote["text"] not in diary["text"]:
            raise ValueError(f"quote not found in {quote['diary_id']}: {quote['text']!r}")


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
