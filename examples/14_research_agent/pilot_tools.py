"""Bounded tools used by the Research Pilot Director."""
import html
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from agents import function_tool
from pydantic import BaseModel, ConfigDict

from lab_llm import (
    ItemBank,
    LLMJob,
    OutputContract,
    load_token_pricing,
    run_jobs,
)
from lab_llm.config import get_model
from study_helpers import estimate_rating_pilot, inspect_rating_study


STUDY_PATH = Path("examples/13_tool_calling/study")
PRICING_PATH = Path("data/model_pricing.csv")
RUN_PATH = Path("runs/research-agent-pilot")


class Rating(BaseModel):
    """The pilot's structured model output."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    rating: float | None


RATING_CONTRACT = OutputContract("agent_pilot_rating", "1", Rating)


@function_tool
def inspect_study() -> str:
    """Inspect the fixed study folder and report its inputs and issues."""
    print("tool: inspect_study()")
    return json.dumps(inspect_rating_study(STUDY_PATH))


@function_tool
def estimate_pilot(pilot_transcripts: int = 3) -> str:
    """Estimate requests and token cost for a small rating pilot."""
    print(f"tool: estimate_pilot(pilot_transcripts={pilot_transcripts})")
    estimate = estimate_rating_pilot(
        STUDY_PATH,
        PRICING_PATH,
        get_model(),
        pilot_transcripts=pilot_transcripts,
    )
    return json.dumps(estimate)


@function_tool(needs_approval=True)
def run_pilot(pilot_transcripts: int = 3) -> str:
    """Run and save a small pilot. This makes paid model requests."""
    if pilot_transcripts < 1:
        raise ValueError("pilot_transcripts must be positive")
    print(f"tool: run_pilot(pilot_transcripts={pilot_transcripts})")
    inspection = inspect_rating_study(STUDY_PATH)
    names = inspection["usable_files"][:pilot_transcripts]
    items = ItemBank.from_csv(STUDY_PATH / "items.csv")
    model = get_model()
    jobs = []

    for name in names:
        transcript = (STUDY_PATH / "transcripts" / name).read_text(
            encoding="utf-8"
        ).strip()
        for item in items:
            jobs.append(LLMJob(
                job_id=f"{Path(name).stem}__{item.item_id}",
                prompt=(
                    f"Requested rating:\n{item.prompt}\n"
                    f"Allowed range: {item.min_value:g} to "
                    f"{item.max_value:g}.\n"
                    f"Scoring values:\n{item.scoring_guide}\n\n"
                    f"Transcript:\n{transcript}"
                ),
                instructions=(
                    "Return the requested rating. Use null when the transcript "
                    "does not contain enough evidence."
                ),
                model=model,
                max_output_tokens=100,
                output_format=RATING_CONTRACT.output_format,
                metadata={
                    "transcript_file": name,
                    "item_id": item.item_id,
                    "min_value": item.min_value,
                    "max_value": item.max_value,
                    "allowed_values": [
                        value for value, _ in item.value_labels
                    ],
                },
            ))

    pricing = load_token_pricing(PRICING_PATH, model)
    records = run_jobs(
        jobs,
        RUN_PATH / "raw_results.jsonl",
        pricing=pricing,
        output_contract=RATING_CONTRACT,
    )
    counts = Counter(record["status"] for record in records)
    return json.dumps({
        "run_path": str(RUN_PATH),
        "requests": len(jobs),
        "statuses": counts,
    })


def _pilot_review() -> dict:
    """Check saved results without another model call."""
    path = RUN_PATH / "raw_results.jsonl"
    if not path.exists():
        return {"status": "not_run", "issues": ["No pilot results found."]}

    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    latest = {record["job_id"]: record for record in records}
    issues = []
    ratings = []

    for record in latest.values():
        if record["status"] != "completed":
            issues.append(f"{record['job_id']}: {record['status']}")
            continue
        rating = (record.get("parsed_output") or {}).get("rating")
        if rating is None:
            issues.append(f"{record['job_id']}: not scored")
            continue

        metadata = record["metadata"]
        value = Decimal(str(rating))
        minimum = Decimal(str(metadata["min_value"]))
        maximum = Decimal(str(metadata["max_value"]))
        allowed = {
            Decimal(str(number))
            for number in metadata.get("allowed_values", [])
        }
        outside_range = not minimum <= value <= maximum
        outside_scale = bool(allowed) and value not in allowed
        if outside_range or outside_scale:
            issues.append(f"{record['job_id']}: invalid rating {value:g}")
            continue
        ratings.append({"job_id": record["job_id"], "rating": float(value)})

    total = len(latest)
    parsed = len(ratings)
    return {
        "status": "checked",
        "requests": total,
        "parsed": parsed,
        "parse_rate": round(parsed / total, 3) if total else 0,
        "issues": issues,
        "ratings": ratings,
    }


@function_tool
def check_pilot() -> str:
    """Validate the saved pilot and summarize any issues."""
    print("tool: check_pilot()")
    return json.dumps(_pilot_review())


@function_tool(needs_approval=True)
def save_review() -> str:
    """Write a small HTML review beside the saved pilot results."""
    print("tool: save_review()")
    review = _pilot_review()
    RUN_PATH.mkdir(parents=True, exist_ok=True)
    issues = "".join(
        f"<li>{html.escape(issue)}</li>" for issue in review.get("issues", [])
    ) or "<li>None.</li>"
    output = RUN_PATH / "review.html"
    output.write_text(
        "<!doctype html><meta charset='utf-8'>"
        "<title>Pilot review</title>"
        "<style>body{font:18px system-ui;max-width:760px;margin:60px auto;"
        "line-height:1.55;color:#163042}strong{color:#087b8f}</style>"
        "<h1>Research pilot review</h1>"
        f"<p><strong>{review.get('parsed', 0)}</strong> parsed of "
        f"<strong>{review.get('requests', 0)}</strong> requests.</p>"
        "<h2>Issues for review</h2>"
        f"<ul>{issues}</ul>",
        encoding="utf-8",
    )
    return json.dumps({"saved": str(output), "review": review})


TOOLS = [
    inspect_study,
    estimate_pilot,
    run_pilot,
    check_pilot,
    save_review,
]
