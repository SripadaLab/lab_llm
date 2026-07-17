"""Tests for the Study Investigator's bounded file access."""
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory
from unittest import TestCase


STUDY_FILES = run_path(
    Path(__file__).parents[1]
    / "examples"
    / "14_research_agent"
    / "study_files.py"
)
list_study_files = STUDY_FILES["list_study_files"]
read_study_file = STUDY_FILES["read_study_file"]


class StudyToolTests(TestCase):
    def test_lists_only_readable_study_files(self):
        with TemporaryDirectory() as directory:
            study = Path(directory)
            (study / "notes.md").write_text("Notes", encoding="utf-8")
            (study / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
            (study / "image.png").write_bytes(b"not an image")

            files = list_study_files(study)

        self.assertEqual(
            [file["path"] for file in files],
            ["notes.md", "table.csv"],
        )

    def test_reads_a_file_inside_the_study(self):
        with TemporaryDirectory() as directory:
            study = Path(directory)
            (study / "notes.md").write_text("Evidence", encoding="utf-8")

            text = read_study_file("notes.md", study)

        self.assertEqual(text, "Evidence")

    def test_blocks_paths_outside_the_study(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            study = root / "study"
            study.mkdir()
            (root / "secret.txt").write_text("secret", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "inside the study"):
                read_study_file("../secret.txt", study)

    def test_blocks_large_files(self):
        with TemporaryDirectory() as directory:
            study = Path(directory)
            (study / "large.txt").write_text("x" * 20_001, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "too large"):
                read_study_file("large.txt", study)
