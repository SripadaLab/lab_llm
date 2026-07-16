"""Offline checks for the multi-step mood-diary workflow."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


PROJECT = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT / "examples/12_mood_diary_workflow"
sys.path.insert(0, str(EXAMPLE))

from report import render_report  # noqa: E402
from workflow import (  # noqa: E402
    _check_membership,
    _verify_quotes,
    load_diaries,
    score_themes,
)


class MoodDiaryWorkflowTests(TestCase):
    def test_loads_the_synthetic_diaries(self):
        diaries = load_diaries(PROJECT / "data/mood_diaries")

        self.assertEqual(len(diaries), 8)
        self.assertEqual(diaries[0]["date"], "2026-06-01")
        self.assertIn("presentation", diaries[0]["text"])

    def test_scores_and_ranks_with_transparent_python(self):
        candidates = [
            self._candidate("c1", "d1", 5),
            self._candidate("c2", "d2", 3),
            self._candidate("c3", "d3", 5),
        ]
        themes = [
            self._theme("theme_01", ["c1", "c2"]),
            self._theme("theme_02", ["c3"]),
        ]

        with TemporaryDirectory() as directory:
            rows = score_themes(
                themes, candidates, 4, Path(directory),
            )

        self.assertEqual(rows[0]["theme_id"], "theme_01")
        self.assertEqual(rows[0]["salience"], 59.0)
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[1]["salience"], 47.5)

    def test_rejects_missing_or_duplicate_theme_membership(self):
        candidates = [
            self._candidate("c1", "d1", 3),
            self._candidate("c2", "d2", 3),
        ]

        with self.assertRaisesRegex(ValueError, "assigned more than once"):
            _check_membership(
                candidates,
                [self._theme("theme_01", ["c1", "c1", "c2"])],
            )
        with self.assertRaisesRegex(ValueError, "membership mismatch"):
            _check_membership(
                candidates,
                [self._theme("theme_01", ["c1"])],
            )
        with self.assertRaisesRegex(ValueError, "at least one candidate ID"):
            _check_membership(
                candidates,
                [
                    self._theme("theme_01", ["c1", "c2"]),
                    self._theme("theme_02", []),
                ],
            )

    def test_rejects_a_quote_not_present_in_its_diary(self):
        diaries = {
            "d1": {"diary_id": "d1", "date": "2026-06-01", "text": "Exact words."}
        }
        quote = {"diary_id": "d1", "date": "2026-06-01", "text": "Invented words."}

        with self.assertRaisesRegex(ValueError, "quote not found"):
            _verify_quotes([quote], diaries)

    def test_renders_scores_and_evidence_as_html(self):
        themes = [self._theme("theme_01", ["c1"])]
        scores = [{
            "theme_id": "theme_01", "diary_count": 1,
            "candidate_count": 1, "mean_importance": 4.0,
            "salience": 52.0, "rank": 1,
        }]
        evidence = [{
            "theme_id": "theme_01",
            "explanation": "Work pressure recurred.",
            "quotes": [{"date": "2026-06-01", "text": "Exact <quote>."}],
            "uncertainty": "Limited entries.",
        }]

        with TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            render_report(themes, scores, evidence, path)
            html = path.read_text(encoding="utf-8")

        self.assertIn("Pressure to perform", html)
        self.assertIn("Work pressure recurred", html)
        self.assertIn("Exact &lt;quote&gt;.", html)

    @staticmethod
    def _candidate(candidate_id, diary_id, importance):
        return {
            "candidate_id": candidate_id,
            "diary_id": diary_id,
            "importance": importance,
        }

    @staticmethod
    def _theme(theme_id, candidate_ids):
        return {
            "theme_id": theme_id,
            "title": "Pressure to perform",
            "description": "Recurring concern about work performance.",
            "candidate_ids": candidate_ids,
        }
