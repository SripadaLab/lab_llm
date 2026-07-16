"""Small helpers for token-based cost and run progress estimates."""
from __future__ import annotations

import csv
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class TokenPricing:
    """Token prices for one model and service tier, in US dollars."""

    model: str
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float
    as_of: str
    service_tier: str = "standard"
    source_url: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("pricing model must be a non-empty string")
        for name in (
            "input_per_million",
            "cached_input_per_million",
            "output_per_million",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not isinstance(self.as_of, str) or not self.as_of.strip():
            raise ValueError("pricing as_of must be a non-empty string")
        if (
            not isinstance(self.service_tier, str)
            or not self.service_tier.strip()
        ):
            raise ValueError("pricing service_tier must be a non-empty string")
        if self.source_url is not None and (
            not isinstance(self.source_url, str) or not self.source_url.strip()
        ):
            raise ValueError("pricing source_url must be a non-empty string")

    def estimate(self, usage: dict[str, Any] | None) -> float | None:
        """Estimate one response's token cost from API-reported usage."""
        if not usage:
            return None

        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if input_tokens is None or output_tokens is None:
            return None

        cached_tokens = usage.get("cached_input_tokens") or 0
        uncached_tokens = max(input_tokens - cached_tokens, 0)
        cost = (
            uncached_tokens * self.input_per_million
            + cached_tokens * self.cached_input_per_million
            + output_tokens * self.output_per_million
        ) / 1_000_000
        return cost

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly copy for a run manifest."""
        return {
            "model": self.model,
            "input_per_million": self.input_per_million,
            "cached_input_per_million": self.cached_input_per_million,
            "output_per_million": self.output_per_million,
            "currency": "USD",
            "as_of": self.as_of,
            "service_tier": self.service_tier,
            "source_url": self.source_url,
        }


def load_token_pricing(
    path: str | Path,
    model: str,
    *,
    service_tier: str = "standard",
) -> TokenPricing:
    """Load one model's rates from an explicit CSV pricing snapshot."""
    path = Path(path)
    required = {
        "model",
        "service_tier",
        "input_per_million",
        "cached_input_per_million",
        "output_per_million",
        "as_of",
        "source_url",
    }

    try:
        with path.open(newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            missing = required - set(reader.fieldnames or [])
            if missing:
                names = ", ".join(sorted(missing))
                raise ValueError(f"{path} is missing columns: {names}")
            matches = [
                row
                for row in reader
                if row["model"].strip() == model
                and row["service_tier"].strip() == service_tier
            ]
    except OSError as exc:
        raise ValueError(f"could not read pricing file: {path}") from exc

    if not matches:
        raise ValueError(
            f"{path} has no pricing for model {model!r} "
            f"and service tier {service_tier!r}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"{path} has duplicate pricing for model {model!r} "
            f"and service tier {service_tier!r}"
        )

    row = matches[0]
    try:
        return TokenPricing(
            model=model,
            service_tier=service_tier,
            input_per_million=float(row["input_per_million"]),
            cached_input_per_million=float(row["cached_input_per_million"]),
            output_per_million=float(row["output_per_million"]),
            as_of=row["as_of"].strip(),
            source_url=row["source_url"].strip(),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"invalid pricing for model {model!r} in {path}: {exc}"
        ) from exc


class RunProgress:
    """Track results as they arrive, regardless of how they were executed.

    A future multiprocessing runner can keep this object in the parent process
    and call ``update()`` whenever a worker returns a saved result.
    """

    def __init__(
        self,
        total_jobs: int,
        pending_jobs: int,
        existing_records: Iterable[dict[str, Any]],
        pricing: TokenPricing | None,
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.total_jobs = total_jobs
        self.remaining = pending_jobs
        self.pricing = pricing
        self._clock = clock
        self._started_at = clock()
        self._attempted = 0

        # Resume includes the cost already recorded for completed jobs.
        self._completed_costs = [
            cost
            for record in existing_records
            if record.get("status") == "completed"
            if (cost := _record_cost(record, pricing)) is not None
        ]

    def update(self, record: dict[str, Any]) -> str:
        """Accept one finished attempt and return a concise status line."""
        self._attempted += 1
        self.remaining = max(self.remaining - 1, 0)

        if record.get("status") == "completed":
            cost = _record_cost(record, self.pricing)
            if cost is not None:
                self._completed_costs.append(cost)

        elapsed = max(self._clock() - self._started_at, 0)
        eta = None
        if self._attempted and self.remaining:
            eta = elapsed / self._attempted * self.remaining
        elif not self.remaining:
            eta = 0.0

        parts = [f"elapsed {_format_duration(elapsed)}"]
        if eta is not None:
            parts.append(f"ETA {_format_duration(eta)}")

        # The projection improves as real responses arrive. Pending jobs use
        # the observed mean cost of completed jobs.
        if self._completed_costs:
            cost_so_far = sum(self._completed_costs)
            mean_cost = cost_so_far / len(self._completed_costs)
            projected_cost = cost_so_far + mean_cost * self.remaining
            parts.append(f"cost ~{_format_dollars(cost_so_far)}")
            parts.append(f"est. total ~{_format_dollars(projected_cost)}")

        return " | ".join(parts)


def add_cost_estimate(
    record: dict[str, Any],
    pricing: TokenPricing | None,
) -> None:
    """Add a transparent, reproducible cost estimate to one saved record."""
    cost = _record_cost(record, pricing)
    record["estimated_cost_usd"] = round(cost, 10) if cost is not None else None


def _record_cost(
    record: dict[str, Any],
    pricing: TokenPricing | None,
) -> float | None:
    """Read a saved estimate, or calculate it for an older record."""
    if pricing is None:
        return None
    saved = record.get("estimated_cost_usd")
    if saved is not None:
        return float(saved)
    return pricing.estimate(record.get("usage"))


def _format_duration(seconds: float) -> str:
    """Format short terminal-friendly elapsed and ETA values."""
    seconds = max(round(seconds), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def _format_dollars(value: float) -> str:
    """Keep tiny research-pilot costs visible instead of rounding to zero."""
    if value < 0.01:
        return f"${value:.4f}"
    return f"${value:.2f}"
