"""Tests for the Research Pilot Director's local study helpers."""

from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory
from unittest import TestCase


HELPERS = run_path(
    Path(__file__).parents[1]
    / "examples"
    / "14_research_agent"
    / "study_helpers.py"
)
inspect_rating_study = HELPERS["inspect_rating_study"]
estimate_rating_pilot = HELPERS["estimate_rating_pilot"]


class StudyTests(TestCase):
    def test_inspects_files_items_and_blank_transcripts(self):
        with TemporaryDirectory() as directory:
            study = Path(directory)
            transcripts = study / "transcripts"
            transcripts.mkdir()
            (transcripts / "T1.txt").write_text("Usable", encoding="utf-8")
            (transcripts / "T2.txt").write_text("\n", encoding="utf-8")
            (study / "items.csv").write_text(
                "item_id,prompt,min_value,max_value,scoring_values\n"
                'anx,Rate anxiety,0,3,"0 = None | 1 = Low | '
                '2 = Medium | 3 = High"\n',
                encoding="utf-8",
            )

            report = inspect_rating_study(study)

        self.assertEqual(report["transcripts_found"], 2)
        self.assertEqual(report["usable_transcripts"], 1)
        self.assertEqual(report["possible_jobs"], 1)
        self.assertEqual(report["scales"]["anx"], [0, 1, 2, 3])
        self.assertFalse(report["ready"])
        self.assertIn("Blank transcripts", report["issues"][0])

    def test_estimates_only_the_requested_pilot(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            study = root / "study"
            transcripts = study / "transcripts"
            transcripts.mkdir(parents=True)
            for number in range(4):
                (transcripts / f"T{number}.txt").write_text(
                    "A short transcript.", encoding="utf-8"
                )
            (study / "items.csv").write_text(
                "item_id,prompt,min_value,max_value\n"
                "anx,Rate anxiety,0,100\n"
                "dep,Rate mood,0,100\n",
                encoding="utf-8",
            )
            pricing = root / "pricing.csv"
            pricing.write_text(
                "model,service_tier,input_per_million,"
                "cached_input_per_million,output_per_million,as_of,source_url\n"
                "test-model,standard,1,0.1,2,2026-01-01,https://example.com\n",
                encoding="utf-8",
            )

            estimate = estimate_rating_pilot(
                study, pricing, "test-model", pilot_transcripts=3
            )

        self.assertEqual(estimate["pilot_transcripts"], 3)
        self.assertEqual(estimate["requests"], 6)
        self.assertGreater(estimate["estimated_cost_usd"], 0)
        self.assertTrue(estimate["estimate_only"])
