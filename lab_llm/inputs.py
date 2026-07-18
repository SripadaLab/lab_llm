"""Small, validated inputs for repeatable research runs."""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Iterator


@dataclass(frozen=True)
class PromptTemplate:
    """A text template with an explicit set of allowed placeholders."""

    text: str
    fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("prompt template must be a non-empty string")
        if not self.fields or any(
            not isinstance(field, str) or not field.strip()
            for field in self.fields
        ):
            raise ValueError("template fields must be non-empty strings")
        if len(self.fields) != len(set(self.fields)):
            raise ValueError("template fields must be unique")

        expected = set(self.fields)
        try:
            parts = list(Formatter().parse(self.text))
        except ValueError as exc:
            raise ValueError(f"invalid prompt template: {exc}") from exc

        found = set()
        for _, field, format_spec, conversion in parts:
            if field is None:
                continue
            if field not in expected:
                raise ValueError(f"unknown prompt placeholder: {{{field}}}")
            if format_spec or conversion:
                raise ValueError(
                    "prompt placeholders cannot use formatting options"
                )
            found.add(field)

        missing = expected - found
        if missing:
            names = ", ".join(f"{{{name}}}" for name in sorted(missing))
            raise ValueError(f"prompt template is missing: {names}")

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        fields: tuple[str, ...],
    ) -> "PromptTemplate":
        """Read and validate a UTF-8 prompt-template file."""
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"could not read prompt template: {path}") from exc
        return cls(text=text, fields=fields)

    def render(self, **values: str) -> str:
        """Insert one string value for every declared placeholder."""
        expected = set(self.fields)
        supplied = set(values)
        if supplied != expected:
            missing = expected - supplied
            extra = supplied - expected
            details = []
            if missing:
                details.append(f"missing: {', '.join(sorted(missing))}")
            if extra:
                details.append(f"unexpected: {', '.join(sorted(extra))}")
            raise ValueError(
                "template values do not match fields; " + "; ".join(details)
            )
        if any(not isinstance(value, str) for value in values.values()):
            raise ValueError("template values must be strings")
        return self.text.format(**values)


@dataclass(frozen=True)
class Transcript:
    """One transcript loaded from one plain-text file."""

    transcript_id: str
    text: str
    filename: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.transcript_id, str)
            or not self.transcript_id.strip()
        ):
            raise ValueError("transcript_id must be a non-empty string")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("transcript text must be a non-empty string")
        if not isinstance(self.filename, str) or not self.filename.strip():
            raise ValueError("transcript filename must be a non-empty string")


@dataclass(frozen=True)
class TranscriptBank:
    """An ordered, uniquely identified collection of transcripts."""

    transcripts: tuple[Transcript, ...]

    def __post_init__(self) -> None:
        transcripts = tuple(self.transcripts)
        object.__setattr__(self, "transcripts", transcripts)
        if not transcripts:
            raise ValueError("transcript bank must contain at least one transcript")
        if any(not isinstance(item, Transcript) for item in transcripts):
            raise ValueError("transcript bank must contain Transcript objects")
        ids = [item.transcript_id for item in transcripts]
        if len(ids) != len(set(ids)):
            raise ValueError("transcript_id values must be unique")

    @classmethod
    def from_directory(cls, directory: str | Path) -> "TranscriptBank":
        """Load one `.txt` transcript per file, ordered by filename."""
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError(f"{directory} is not a directory")

        files = sorted(
            path for path in directory.glob("*.txt") if path.is_file()
        )
        if not files:
            raise ValueError(f"{directory} contains no .txt transcript files")

        transcripts = []
        for path in files:
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                raise ValueError(f"{path} is empty")
            transcripts.append(
                Transcript(
                    transcript_id=path.stem,
                    filename=path.name,
                    text=text,
                )
            )
        return cls(tuple(transcripts))

    def __iter__(self) -> Iterator[Transcript]:
        return iter(self.transcripts)

    def __len__(self) -> int:
        return len(self.transcripts)


@dataclass(frozen=True)
class Item:
    """One named item to apply to every transcript."""

    item_id: str
    prompt: str
    min_value: float | None
    max_value: float | None
    scoring_values: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ValueError("item_id must be a non-empty string")
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("item prompt must be a non-empty string")
        for name in ("min_value", "max_value"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"item {name} must be a number or null")
            if not math.isfinite(value):
                raise ValueError(f"item {name} must be finite")

        bounds = (self.min_value, self.max_value)
        if (self.min_value is None) != (self.max_value is None):
            raise ValueError(
                "item min_value and max_value must both be set or both be blank"
            )
        if self.min_value is not None and self.min_value >= self.max_value:
            raise ValueError("item min_value must be less than max_value")

        # Optional Likert values use a compact, CSV-friendly format:
        # "0 = Not at all | 1 = Several days | 2 = Nearly every day"
        values = self.value_labels
        responses = self.acceptable_responses
        if values and self.min_value is None:
            raise ValueError(
                "numeric scoring_values require min_value and max_value"
            )
        if values and (values[0][0], values[-1][0]) != bounds:
            raise ValueError(
                "scoring_values must start at min_value and end at max_value"
            )
        if responses and self.min_value is not None:
            raise ValueError(
                "text scoring_values require blank min_value and max_value"
            )
        if not values and not responses and self.min_value is None:
            raise ValueError(
                "items without numeric bounds must define text scoring_values"
            )

    @property
    def value_labels(self) -> tuple[tuple[float, str], ...]:
        """Return exact scoring values and their labels."""
        if not isinstance(self.scoring_values, str):
            raise ValueError("item scoring_values must be a string")
        if not self.scoring_values.strip():
            return ()

        entries = [entry.strip() for entry in self.scoring_values.split("|")]
        has_labels = ["=" in entry for entry in entries]
        if not all(has_labels):
            if any(has_labels):
                raise ValueError(
                    "scoring_values cannot mix numeric labels and text responses"
                )
            return ()

        values = []
        for entry in entries:
            number, separator, label = entry.partition("=")
            if not separator or not number.strip() or not label.strip():
                raise ValueError(
                    'scoring_values must use "number = label | number = label"'
                )
            try:
                value = float(number.strip())
            except ValueError as exc:
                raise ValueError("scoring values must be numbers") from exc
            if not math.isfinite(value):
                raise ValueError("scoring values must be finite")
            values.append((value, label.strip()))

        numbers = [value for value, _ in values]
        if numbers != sorted(set(numbers)):
            raise ValueError("scoring values must be unique and increasing")
        return tuple(values)

    @property
    def acceptable_responses(self) -> tuple[str, ...]:
        """Return exact user-defined text responses, in declared order."""
        if not isinstance(self.scoring_values, str):
            raise ValueError("item scoring_values must be a string")
        if not self.scoring_values.strip():
            return ()

        entries = tuple(entry.strip() for entry in self.scoring_values.split("|"))
        if any("=" in entry for entry in entries):
            return ()
        if any(not entry for entry in entries):
            raise ValueError("text scoring values must be non-empty")
        if len(entries) != len(set(entries)):
            raise ValueError("text scoring values must be unique")
        return entries

    @property
    def allowed_values(self) -> tuple[float | str, ...]:
        """Return exact allowed values, when the item is discrete."""
        if self.acceptable_responses:
            return self.acceptable_responses
        return tuple(value for value, _ in self.value_labels)

    @property
    def scoring_guide(self) -> str:
        """Format a scale for insertion into a model prompt."""
        if self.acceptable_responses:
            choices = "\n".join(f"- {value}" for value in self.acceptable_responses)
            return f"Return exactly one of these text responses:\n{choices}"
        if not self.value_labels:
            return "Any number in the allowed range."
        return "\n".join(
            f"{value:g} = {label}" for value, label in self.value_labels
        )

    @property
    def response_requirements(self) -> str:
        """Format only the requirements that apply to this response type."""
        if self.acceptable_responses:
            return self.scoring_guide
        return (
            f"Numeric range: {self.min_value:g} to {self.max_value:g}.\n"
            f"{self.scoring_guide}"
        )


@dataclass(frozen=True)
class ItemBank:
    """An ordered, uniquely identified collection of items."""

    items: tuple[Item, ...]

    def __post_init__(self) -> None:
        items = tuple(self.items)
        object.__setattr__(self, "items", items)
        if not items:
            raise ValueError("item bank must contain at least one item")
        if any(not isinstance(item, Item) for item in items):
            raise ValueError("item bank must contain Item objects")
        ids = [item.item_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("item_id values must be unique")

    @classmethod
    def from_csv(cls, path: str | Path) -> "ItemBank":
        """Load numeric or categorical rating items from a UTF-8 CSV file."""
        path = Path(path)
        try:
            with path.open(newline="", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                required = {"item_id", "prompt", "min_value", "max_value"}
                missing = required - set(reader.fieldnames or [])
                if missing:
                    names = ", ".join(sorted(missing))
                    raise ValueError(f"{path} is missing columns: {names}")

                items = []
                for row_number, row in enumerate(reader, start=2):
                    item_id = (row.get("item_id") or "").strip()
                    prompt = (row.get("prompt") or "").strip()
                    min_value = (row.get("min_value") or "").strip()
                    max_value = (row.get("max_value") or "").strip()
                    scoring_values = (row.get("scoring_values") or "").strip()
                    if not item_id:
                        raise ValueError(f"{path}:{row_number} has a blank item_id")
                    if not prompt:
                        raise ValueError(f"{path}:{row_number} has a blank prompt")
                    try:
                        item = Item(
                            item_id=item_id,
                            prompt=prompt,
                            min_value=float(min_value) if min_value else None,
                            max_value=float(max_value) if max_value else None,
                            scoring_values=scoring_values,
                        )
                    except ValueError as exc:
                        raise ValueError(f"{path}:{row_number}: {exc}") from exc
                    items.append(item)
        except OSError as exc:
            raise ValueError(f"could not read item bank: {path}") from exc

        if not items:
            raise ValueError(f"{path} has no data rows")
        return cls(tuple(items))

    def __iter__(self) -> Iterator[Item]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)
