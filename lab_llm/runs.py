"""Standard command line and durable files for batch runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def parse_run_args(
    argv: Sequence[str] | None = None,
    *,
    transcripts_path: Path,
    items_path: Path,
    instructions_path: Path,
    pricing_path: Path,
):
    """Read the standard options used by rating batches."""
    parser = argparse.ArgumentParser(
        description="Rate every transcript on every survey item."
    )
    parser.add_argument("--run-name", required=True, type=_run_name)
    parser.add_argument("--pricing-file", type=Path, default=pricing_path)
    parser.add_argument(
        "--transcripts", type=Path, default=transcripts_path
    )
    parser.add_argument("--items", type=Path, default=items_path)
    parser.add_argument(
        "--instructions",
        type=Path,
        default=instructions_path,
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be a positive integer")
    return args


def write_job_plan(jobs, path: Path) -> None:
    """Save every exact request before the first API call."""
    lines = []
    for job in jobs:
        lines.append(json.dumps({
            "job_id": job.job_id,
            "model": job.model,
            "instructions": job.instructions,
            "input": job.prompt,
            "max_output_tokens": job.max_output_tokens,
            "output_format": job.output_format,
            "metadata": job.metadata,
        }, ensure_ascii=False, sort_keys=True))
    _write_unchanged(path, "\n".join(lines) + "\n", "jobs")


def write_manifest(
    jobs,
    model,
    sources,
    pricing,
    contract,
    path: Path,
    *,
    settings=None,
) -> None:
    """Save the inputs needed to understand or reproduce the run."""
    details = {
        "run_name": path.parent.name,
        "model": model,
        "endpoint": "/v1/responses",
        "expected_jobs": len(jobs),
        "output_contract": contract.contract_id,
        "pricing": pricing.as_dict(),
        "sources": {
            name: _source_details(source)
            for name, source in sources.items()
        },
    }
    if settings is not None:
        details["settings"] = settings

    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing.pop("created_at", None)
        if existing != details:
            raise ValueError(f"{path} does not match the current inputs")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(),
        **details,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _run_name(value: str) -> str:
    """Accept a safe folder name, not a path."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise argparse.ArgumentTypeError(
            "use letters, numbers, dots, underscores, or hyphens"
        )
    return value


def _source_details(path) -> dict:
    """Record a file, or every text file in a folder."""
    path = Path(path)
    if path.is_dir():
        files = sorted(file for file in path.glob("*.txt") if file.is_file())
        return {
            "path": str(path),
            "files": [
                {"path": str(file), "sha256": _file_hash(file)}
                for file in files
            ],
        }
    return {"path": str(path), "sha256": _file_hash(path)}


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_unchanged(path: Path, content: str, label: str) -> None:
    """Create a run file once; reject changed work on resume."""
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"{path} does not match the current {label}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
