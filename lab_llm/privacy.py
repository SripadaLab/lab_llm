"""Local text de-identification with OpenAI Privacy Filter.

The optional ``opf`` dependency is imported only when a ``Deidentifier`` first
runs. Importing ``lab_llm`` therefore does not download a model or require the
privacy extra.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .errors import LabLLMError


PRIVACY_LABELS = frozenset({
    "account_number",
    "private_address",
    "private_email",
    "private_person",
    "private_phone",
    "private_url",
    "private_date",
    "secret",
})


class PrivacyFilterUnavailableError(LabLLMError):
    """The optional local Privacy Filter runtime is not installed."""


@dataclass(frozen=True)
class IdentifierMatch:
    """One locally detected identifier and the placeholder that replaced it."""

    label: str
    start: int
    end: int
    original: str
    replacement: str


@dataclass(frozen=True)
class DeidentificationSummary:
    """Audit counts that omit original text and detected identifier values."""

    text_count: int
    identifier_count: int
    counts_by_label: dict[str, int]
    warnings: tuple[str, ...] = ()
    labels_applied: tuple[str, ...] = ()

    @classmethod
    def combine(
        cls,
        summaries: Iterable["DeidentificationSummary"],
    ) -> "DeidentificationSummary":
        """Combine summaries without retaining the identifiers themselves."""
        summaries = tuple(summaries)
        counts: Counter[str] = Counter()
        warnings: list[str] = []
        labels_applied: set[str] = set()
        for summary in summaries:
            counts.update(summary.counts_by_label)
            labels_applied.update(summary.labels_applied)
            for warning in summary.warnings:
                if warning not in warnings:
                    warnings.append(warning)
        return cls(
            text_count=sum(summary.text_count for summary in summaries),
            identifier_count=sum(
                summary.identifier_count for summary in summaries
            ),
            counts_by_label=dict(sorted(counts.items())),
            warnings=tuple(warnings),
            labels_applied=tuple(sorted(labels_applied)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe audit payload with no original identifiers."""
        return {
            "text_count": self.text_count,
            "identifier_count": self.identifier_count,
            "counts_by_label": dict(self.counts_by_label),
            "warnings": list(self.warnings),
            "labels_applied": list(self.labels_applied),
        }


@dataclass(frozen=True)
class DeidentificationResult:
    """Filtered text plus an optional, local-only review of its replacements."""

    text: str
    matches: tuple[IdentifierMatch, ...]
    warning: str | None = None
    labels_applied: tuple[str, ...] = ()

    @property
    def summary(self) -> DeidentificationSummary:
        """Return counts suitable for logs without copying original PII."""
        counts = Counter(match.label for match in self.matches)
        return DeidentificationSummary(
            text_count=1,
            identifier_count=len(self.matches),
            counts_by_label=dict(sorted(counts.items())),
            warnings=(self.warning,) if self.warning else (),
            labels_applied=self.labels_applied,
        )

    def preview(self, *, reveal_original: bool = True) -> str:
        """Format a local review; revealing originals can expose PII on screen."""
        lines = [self.text, "", "Detected identifiers:"]
        if not self.matches:
            lines.append("- none")
        for match in self.matches:
            original = repr(match.original) if reveal_original else "[hidden]"
            lines.append(
                f"- {match.label}: {original} -> {match.replacement}"
            )
        if self.warning:
            lines.extend(("", f"Warning: {self.warning}"))
        return "\n".join(lines)


@dataclass(frozen=True)
class DeidentifiedRecords:
    """Copied records with selected text fields filtered locally."""

    records: tuple[dict[str, Any], ...]
    summary: DeidentificationSummary


@dataclass(frozen=True)
class DeidentifiedInput:
    """A copied Responses API input value and its non-identifying summary."""

    value: Any
    summary: DeidentificationSummary


class Deidentifier:
    """Reusable local Privacy Filter with stable, typed placeholders.

    Reuse one instance across related records so repeated identifiers receive
    the same placeholder, such as ``[PRIVATE_PERSON_1]``. The raw-to-placeholder
    mapping remains only in this Python process.
    """

    def __init__(
        self,
        *,
        checkpoint: str | Path | None = None,
        device: str = "cpu",
        labels: Iterable[str] | None = None,
        calibration_path: str | Path | None = None,
        engine: Any | None = None,
    ) -> None:
        selected_labels = PRIVACY_LABELS if labels is None else frozenset(labels)
        if not selected_labels:
            raise ValueError("labels must contain at least one privacy label")
        unknown = selected_labels - PRIVACY_LABELS
        if unknown:
            raise ValueError(
                "unknown privacy labels: " + ", ".join(sorted(unknown))
            )
        if device not in {"cpu", "cuda"}:
            raise ValueError("device must be 'cpu' or 'cuda'")

        self.checkpoint = str(Path(checkpoint).expanduser()) if checkpoint else None
        self.device = device
        self.labels = selected_labels
        self.calibration_path = (
            str(Path(calibration_path).expanduser())
            if calibration_path is not None
            else None
        )
        self._engine = engine
        self._replacements: dict[tuple[str | None, str, str], str] = {}
        self._label_counts: Counter[tuple[str | None, str]] = Counter()

    def deidentify(
        self,
        text: str,
        *,
        scope: str | None = None,
    ) -> DeidentificationResult:
        """Replace identifiers, keeping placeholders stable within ``scope``.

        Calls without a scope share one mapping, preserving the original
        behavior. A named scope starts its own placeholder numbering while
        continuing to reuse the same loaded Privacy Filter model.
        """
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if scope is not None and (
            not isinstance(scope, str) or not scope.strip()
        ):
            raise ValueError("scope must be a non-empty string or None")
        if not text:
            return DeidentificationResult(
                text="",
                matches=(),
                labels_applied=tuple(sorted(self.labels)),
            )

        result = self._get_engine().redact(text)
        if isinstance(result, str) or not hasattr(result, "detected_spans"):
            raise RuntimeError(
                "Privacy Filter must return structured detected spans"
            )

        source = getattr(result, "text", text)
        spans = [
            span
            for span in result.detected_spans
            if str(span.label) in self.labels
        ]
        spans.sort(key=lambda span: (int(span.start), int(span.end)))

        pieces: list[str] = []
        matches: list[IdentifierMatch] = []
        cursor = 0
        for span in spans:
            label = str(span.label)
            start = int(span.start)
            end = int(span.end)
            if start < cursor or start < 0 or end <= start or end > len(source):
                raise RuntimeError(
                    "Privacy Filter returned invalid or overlapping spans; "
                    "no text was sent"
                )
            original = source[start:end]
            replacement = self._replacement_for(label, original, scope)
            pieces.extend((source[cursor:start], replacement))
            matches.append(
                IdentifierMatch(
                    label=label,
                    start=start,
                    end=end,
                    original=original,
                    replacement=replacement,
                )
            )
            cursor = end
        pieces.append(source[cursor:])

        return DeidentificationResult(
            text="".join(pieces),
            matches=tuple(matches),
            warning=getattr(result, "warning", None),
            labels_applied=tuple(sorted(self.labels)),
        )

    def _replacement_for(
        self,
        label: str,
        original: str,
        scope: str | None,
    ) -> str:
        normalized = " ".join(original.casefold().split())
        key = (scope, label, normalized)
        if key not in self._replacements:
            counter_key = (scope, label)
            self._label_counts[counter_key] += 1
            self._replacements[key] = (
                f"[{label.upper()}_{self._label_counts[counter_key]}]"
            )
        return self._replacements[key]

    def _get_engine(self):
        if self._engine is None:
            self._engine = self._build_engine()
        return self._engine

    def _build_engine(self):
        try:
            from opf import OPF
        except ImportError as exc:
            raise PrivacyFilterUnavailableError(
                "OpenAI Privacy Filter is not installed. Install the optional "
                "workshop dependency with: pip install -e '.[privacy]'"
            ) from exc

        engine = OPF(
            model=self.checkpoint,
            device=self.device,
            output_mode="typed",
            output_text_only=False,
        )
        if self.calibration_path is not None:
            engine.set_viterbi_decoder(calibration_path=self.calibration_path)
        return engine


def deidentify_text(
    text: str,
    *,
    deidentifier: Deidentifier | None = None,
) -> DeidentificationResult:
    """Filter one text locally; reuse a ``Deidentifier`` for related texts."""
    return (deidentifier or Deidentifier()).deidentify(text)


def deidentify_records(
    records: Iterable[Mapping[str, Any]],
    *,
    fields: Sequence[str],
    deidentifier: Deidentifier | None = None,
) -> DeidentifiedRecords:
    """Filter selected top-level text fields in copied CSV/JSON-style records."""
    fields = tuple(fields)
    if not fields or any(not isinstance(field, str) or not field for field in fields):
        raise ValueError("fields must contain non-empty field names")
    if len(fields) != len(set(fields)):
        raise ValueError("fields must be unique")

    deidentifier = deidentifier or Deidentifier()
    filtered: list[dict[str, Any]] = []
    summaries: list[DeidentificationSummary] = []
    for number, record in enumerate(records, start=1):
        if not isinstance(record, Mapping):
            raise TypeError(f"record {number} must be a mapping")
        copied = dict(record)
        for field in fields:
            if field not in copied:
                raise ValueError(f"record {number} is missing field {field!r}")
            value = copied[field]
            if value is None:
                continue
            if not isinstance(value, str):
                raise TypeError(
                    f"record {number} field {field!r} must be text or null"
                )
            result = deidentifier.deidentify(value)
            copied[field] = result.text
            summaries.append(result.summary)
        filtered.append(copied)
    return DeidentifiedRecords(
        records=tuple(filtered),
        summary=DeidentificationSummary.combine(summaries),
    )


def deidentify_responses_input(
    value: Any,
    *,
    deidentifier: Deidentifier | None = None,
) -> DeidentifiedInput:
    """Copy and filter text-bearing fields in a Responses API input value.

    IDs, roles, item types, file references, and SDK response objects are left
    untouched. Text strings, message content, and local function-call output
    are filtered.
    """
    deidentifier = deidentifier or Deidentifier()
    summaries: list[DeidentificationSummary] = []

    def filter_text(text: str) -> str:
        result = deidentifier.deidentify(text)
        summaries.append(result.summary)
        return result.text

    def walk(
        item: Any,
        *,
        text_value: bool = False,
        all_strings: bool = False,
    ) -> Any:
        if isinstance(item, str):
            return filter_text(item) if text_value or all_strings else item
        if isinstance(item, list):
            return [
                walk(
                    child,
                    text_value=text_value,
                    all_strings=all_strings,
                )
                for child in item
            ]
        if isinstance(item, tuple):
            return tuple(
                walk(
                    child,
                    text_value=text_value,
                    all_strings=all_strings,
                )
                for child in item
            )
        if isinstance(item, Mapping):
            item_type = item.get("type")
            copied = {}
            for key, child in item.items():
                function_output = (
                    key == "output" and item_type == "function_call_output"
                )
                contains_text = (
                    all_strings
                    or key in {"input", "content", "text"}
                    or function_output
                )
                copied[key] = walk(
                    child,
                    text_value=contains_text,
                    all_strings=all_strings or function_output,
                )
            return copied
        return item

    filtered = walk(value, text_value=True)
    return DeidentifiedInput(
        value=filtered,
        summary=DeidentificationSummary.combine(summaries),
    )
