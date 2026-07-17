"""Study-specific helpers for the Research Pilot Director example."""
from pathlib import Path
from statistics import mean

from lab_llm import ItemBank, load_token_pricing


def inspect_rating_study(study_path: str | Path) -> dict:
    """Inspect this example's transcript-by-item study without model calls."""
    study_path = Path(study_path)
    transcript_path = study_path / "transcripts"
    issues = []

    files = sorted(transcript_path.glob("*.txt"))
    blank_files = [
        path.name
        for path in files
        if not path.read_text(encoding="utf-8").strip()
    ]
    usable_files = [path for path in files if path.name not in blank_files]
    if not files:
        issues.append("No transcript .txt files found.")
    if blank_files:
        issues.append(f"Blank transcripts: {', '.join(blank_files)}")

    try:
        items = ItemBank.from_csv(study_path / "items.csv")
    except ValueError as exc:
        items = ()
        issues.append(str(exc))

    scales = {
        item.item_id: (
            [value for value, _ in item.value_labels]
            if item.value_labels
            else [item.min_value, item.max_value]
        )
        for item in items
    }
    return {
        "study": study_path.name,
        "transcripts_found": len(files),
        "usable_transcripts": len(usable_files),
        "usable_files": [path.name for path in usable_files],
        "items": len(items),
        "item_ids": [item.item_id for item in items],
        "scales": scales,
        "possible_jobs": len(usable_files) * len(items),
        "ready": not issues,
        "issues": issues,
    }


def estimate_rating_pilot(
    study_path: str | Path,
    pricing_path: str | Path,
    model: str,
    *,
    pilot_transcripts: int = 3,
    output_tokens_per_request: int = 100,
) -> dict:
    """Estimate this example's pilot from file sizes and saved pricing."""
    if pilot_transcripts < 1:
        raise ValueError("pilot_transcripts must be positive")

    study_path = Path(study_path)
    inspection = inspect_rating_study(study_path)
    selected = min(pilot_transcripts, inspection["usable_transcripts"])
    requests = selected * inspection["items"]
    files = [
        study_path / "transcripts" / name
        for name in inspection["usable_files"][:selected]
    ]

    # A rough planning estimate. Four characters per token, plus prompt overhead.
    mean_characters = (
        mean(len(path.read_text(encoding="utf-8")) for path in files)
        if files else 0
    )
    input_tokens = round(mean_characters / 4) + 250
    pricing = load_token_pricing(pricing_path, model)
    cost_per_request = pricing.estimate({
        "input_tokens": input_tokens,
        "output_tokens": output_tokens_per_request,
    })

    return {
        "pilot_transcripts": selected,
        "items": inspection["items"],
        "requests": requests,
        "estimated_input_tokens_per_request": input_tokens,
        "max_output_tokens_per_request": output_tokens_per_request,
        "estimated_cost_usd": round((cost_per_request or 0) * requests, 6),
        "model": model,
        "estimate_only": True,
    }
