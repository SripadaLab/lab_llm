"""Tests for the optional local de-identification layer."""

from dataclasses import dataclass
from types import SimpleNamespace
from unittest import TestCase

from lab_llm import (
    Deidentifier,
    deidentify_records,
    deidentify_responses_input,
)


@dataclass(frozen=True)
class FakeSpan:
    label: str
    start: int
    end: int


class PatternEngine:
    """Small deterministic stand-in for the local OPF model."""

    def __init__(self, patterns, *, warning=None):
        self.patterns = patterns
        self.warning = warning
        self.calls = []

    def redact(self, text):
        self.calls.append(text)
        spans = []
        for original, label in self.patterns:
            start = 0
            while True:
                found = text.find(original, start)
                if found < 0:
                    break
                spans.append(FakeSpan(label, found, found + len(original)))
                start = found + len(original)
        spans.sort(key=lambda span: (span.start, span.end))
        return SimpleNamespace(
            text=text,
            detected_spans=tuple(spans),
            warning=self.warning,
        )


class PrivacyTests(TestCase):
    def test_replaces_repeated_identifiers_with_stable_typed_placeholders(self):
        engine = PatternEngine([
            ("Alice Smith", "private_person"),
            ("alice@example.com", "private_email"),
        ])
        deidentifier = Deidentifier(engine=engine)

        first = deidentifier.deidentify(
            "Alice Smith emailed alice@example.com. Alice Smith followed up."
        )
        second = deidentifier.deidentify("Ask Alice Smith again.")

        self.assertEqual(
            first.text,
            "[PRIVATE_PERSON_1] emailed [PRIVATE_EMAIL_1]. "
            "[PRIVATE_PERSON_1] followed up.",
        )
        self.assertEqual(second.text, "Ask [PRIVATE_PERSON_1] again.")
        self.assertEqual(first.summary.identifier_count, 3)
        self.assertEqual(
            first.summary.counts_by_label,
            {"private_email": 1, "private_person": 2},
        )
        self.assertEqual(
            [match.original for match in first.matches],
            ["Alice Smith", "alice@example.com", "Alice Smith"],
        )

    def test_scopes_reset_numbering_and_stay_stable_within_each_scope(self):
        deidentifier = Deidentifier(engine=PatternEngine([
            ("Alice Smith", "private_person"),
            ("Bob Jones", "private_person"),
        ]))

        self.assertEqual(
            deidentifier.deidentify("Alice Smith", scope="T1").text,
            "[PRIVATE_PERSON_1]",
        )
        self.assertEqual(
            deidentifier.deidentify("Bob Jones", scope="T2").text,
            "[PRIVATE_PERSON_1]",
        )
        self.assertEqual(
            deidentifier.deidentify("Bob Jones", scope="T1").text,
            "[PRIVATE_PERSON_2]",
        )
        self.assertEqual(
            deidentifier.deidentify("Alice Smith", scope="T1").text,
            "[PRIVATE_PERSON_1]",
        )

    def test_selected_labels_can_preserve_research_relevant_fields(self):
        engine = PatternEngine([
            ("Alice Smith", "private_person"),
            ("1990-01-02", "private_date"),
        ])
        deidentifier = Deidentifier(
            engine=engine,
            labels={"private_person"},
        )

        result = deidentifier.deidentify("Alice Smith: 1990-01-02")

        self.assertEqual(result.text, "[PRIVATE_PERSON_1]: 1990-01-02")
        self.assertEqual(len(result.matches), 1)

    def test_preview_can_hide_original_identifiers(self):
        deidentifier = Deidentifier(
            engine=PatternEngine([("Alice Smith", "private_person")])
        )
        result = deidentifier.deidentify("Hello Alice Smith")

        revealed = result.preview()
        hidden = result.preview(reveal_original=False)

        self.assertIn("'Alice Smith' -> [PRIVATE_PERSON_1]", revealed)
        self.assertNotIn("Alice Smith", hidden)
        self.assertIn("[hidden] -> [PRIVATE_PERSON_1]", hidden)

    def test_warning_is_kept_in_local_result_and_nonidentifying_summary(self):
        warning = "Tokenizer round-trip differed."
        result = Deidentifier(
            engine=PatternEngine([], warning=warning)
        ).deidentify("No identifiers")

        self.assertEqual(result.warning, warning)
        self.assertEqual(result.summary.warnings, (warning,))
        self.assertNotIn("No identifiers", str(result.summary.to_dict()))

    def test_invalid_or_overlapping_spans_fail_closed(self):
        engine = SimpleNamespace(
            redact=lambda text: SimpleNamespace(
                text=text,
                detected_spans=(
                    FakeSpan("private_person", 0, 5),
                    FakeSpan("private_email", 3, 8),
                ),
                warning=None,
            )
        )

        with self.assertRaisesRegex(RuntimeError, "no text was sent"):
            Deidentifier(engine=engine).deidentify("Alice123")

    def test_filters_selected_record_fields_without_mutating_sources(self):
        source = [
            {"participant_id": "P01", "note": "Met Alice Smith", "score": 4},
            {"participant_id": "P02", "note": "Alice Smith called", "score": 3},
        ]
        result = deidentify_records(
            source,
            fields=("note",),
            deidentifier=Deidentifier(
                engine=PatternEngine([("Alice Smith", "private_person")])
            ),
        )

        self.assertEqual(source[0]["note"], "Met Alice Smith")
        self.assertEqual(
            result.records[0]["note"],
            "Met [PRIVATE_PERSON_1]",
        )
        self.assertEqual(
            result.records[1]["note"],
            "[PRIVATE_PERSON_1] called",
        )
        self.assertEqual(result.summary.identifier_count, 2)

    def test_filters_responses_input_text_but_preserves_protocol_fields(self):
        value = [
            {
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": "file_Alice_Smith"},
                    {"type": "input_text", "text": "Review Alice Smith"},
                ],
            },
            {
                "type": "function_call_output",
                "call_id": "call_Alice_Smith",
                "output": {
                    "participant": "Alice Smith",
                    "finding": "Alice Smith was found",
                },
            },
        ]
        result = deidentify_responses_input(
            value,
            deidentifier=Deidentifier(
                engine=PatternEngine([("Alice Smith", "private_person")])
            ),
        )

        first_content = result.value[0]["content"]
        self.assertEqual(first_content[0]["file_id"], "file_Alice_Smith")
        self.assertEqual(
            first_content[1]["text"],
            "Review [PRIVATE_PERSON_1]",
        )
        self.assertEqual(result.value[1]["call_id"], "call_Alice_Smith")
        self.assertEqual(
            result.value[1]["output"],
            {
                "participant": "[PRIVATE_PERSON_1]",
                "finding": "[PRIVATE_PERSON_1] was found",
            },
        )
        self.assertEqual(result.summary.identifier_count, 3)

    def test_rejects_unknown_labels_and_bad_record_fields(self):
        with self.assertRaisesRegex(ValueError, "unknown privacy labels"):
            Deidentifier(engine=PatternEngine([]), labels={"medical_record"})

        with self.assertRaisesRegex(ValueError, "missing field"):
            deidentify_records(
                [{"note": "hello"}],
                fields=("missing",),
                deidentifier=Deidentifier(engine=PatternEngine([])),
            )
