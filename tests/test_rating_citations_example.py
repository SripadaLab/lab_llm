"""Offline tests for the citation-enabled ratings batch example."""

import csv
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = (
    PROJECT
    / "examples/08_sequential_ratings/example_with_citations.py"
)
SPEC = importlib.util.spec_from_file_location("rating_citations_example", SCRIPT)
example = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(example)


class RatingCitationsExampleTests(TestCase):
    def test_contract_limits_scored_evidence_to_one_quote(self):
        example.RatingWithCitations.model_rebuild(
            _types_namespace={
                "Citation": example.Citation,
                "Justification": example.Justification,
            }
        )
        schema = example.RatingWithCitations.model_json_schema()
        justifications = schema["properties"]["justifications"]
        justification = schema["$defs"]["Justification"]
        citations = justification["properties"]["citations"]

        self.assertEqual(justifications["maxItems"], 1)
        self.assertEqual(citations["minItems"], 1)
        self.assertEqual(citations["maxItems"], 1)

    def test_accepts_an_exact_quote_from_the_sent_transcript(self):
        record = self._record("I called my sister", "I called my sister today.")

        status, errors, citations = example.audit_citations(record)

        self.assertEqual(status, "passed")
        self.assertEqual(errors, [])
        self.assertTrue(citations[0]["quote_verified"])

    def test_rejects_an_invented_quote(self):
        record = self._record("Words never spoken", "Exact transcript words.")

        status, errors, citations = example.audit_citations(record)

        self.assertEqual(status, "failed")
        self.assertIn("not an exact quote", errors[0])
        self.assertFalse(citations[0]["quote_verified"])

    def test_checks_the_filtered_request_when_privacy_is_enabled(self):
        record = self._record(
            "I spoke with [PRIVATE_PERSON_1]",
            "I spoke with [PRIVATE_PERSON_1] yesterday.",
        )

        status, _, citations = example.audit_citations(record)

        self.assertEqual(status, "passed")
        self.assertTrue(citations[0]["quote_verified"])

    def test_does_not_accept_text_outside_the_transcript_section(self):
        record = self._record(
            "Rate depressed mood.",
            "The transcript does not repeat the item prompt.",
        )

        status, errors, _ = example.audit_citations(record)

        self.assertEqual(status, "failed")
        self.assertTrue(errors)

    def test_writes_job_and_citation_level_exports(self):
        records = [self._record("Exact words", "Exact words are here.")]

        with TemporaryDirectory() as directory:
            run_dir = Path(directory)
            failures = example.write_citation_exports(records, run_dir)
            with (run_dir / "ratings_with_citations.csv").open(
                newline="",
                encoding="utf-8",
            ) as file:
                rating = next(csv.DictReader(file))
            with (run_dir / "citations.csv").open(
                newline="",
                encoding="utf-8",
            ) as file:
                citation = next(csv.DictReader(file))

        self.assertEqual(failures, 0)
        self.assertEqual(rating["citation_validation"], "passed")
        self.assertEqual(json.loads(rating["citations_json"]), ["Exact words"])
        self.assertEqual(citation["quote"], "Exact words")
        self.assertEqual(citation["quote_verified"], "True")

    @staticmethod
    def _record(quote, transcript):
        return {
            "job_id": "transcript-T1__item-I1",
            "status": "completed",
            "metadata": {
                "transcript_id": "T1",
                "transcript_file": "T1.txt",
                "item_id": "I1",
            },
            "request": {
                "input": (
                    "Requested response:\nRate depressed mood.\n"
                    "Response requirements:\nNumeric range: 0 to 100.\n"
                    "\nTranscript:\n"
                    + transcript
                ),
            },
            "parsed_output": {
                "rating": 42,
                "justifications": [{
                    "explanation": "The quote supports the rating.",
                    "citations": [{"text": quote}],
                }],
            },
        }
