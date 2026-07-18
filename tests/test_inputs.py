"""Tests for prompt templates, transcript banks, and item banks."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from lab_llm import Item, ItemBank, PromptTemplate, Transcript, TranscriptBank


class PromptTemplateTests(TestCase):
    def test_loads_and_renders_an_explicit_template(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "prompt.txt"
            path.write_text(
                "Item: {item}\nTranscript: {transcript}\n",
                encoding="utf-8",
            )
            template = PromptTemplate.from_file(
                path,
                fields=("item", "transcript"),
            )

        rendered = template.render(item="Rate mood", transcript="Hello")
        self.assertEqual(rendered, "Item: Rate mood\nTranscript: Hello\n")

    def test_rejects_unknown_missing_or_formatted_placeholders(self):
        for text, message in (
            ("{item}\n{unknown}", "unknown"),
            ("{item}", "missing"),
            ("{item!r}\n{transcript}", "formatting"),
        ):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, message):
                    PromptTemplate(
                        text,
                        fields=("item", "transcript"),
                    )

    def test_render_requires_exactly_the_declared_string_values(self):
        template = PromptTemplate("{item}", fields=("item",))

        with self.assertRaisesRegex(ValueError, "missing"):
            template.render()
        with self.assertRaisesRegex(ValueError, "unexpected"):
            template.render(item="One", extra="Two")
        with self.assertRaisesRegex(ValueError, "must be strings"):
            template.render(item=1)


class TranscriptBankTests(TestCase):
    def test_reads_one_text_file_per_transcript_in_filename_order(self):
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "transcript_02.txt").write_text(
                "Second transcript\n",
                encoding="utf-8",
            )
            (directory / "transcript_01.txt").write_text(
                "First transcript\n",
                encoding="utf-8",
            )
            (directory / "notes.csv").write_text("ignored", encoding="utf-8")

            bank = TranscriptBank.from_directory(directory)

        self.assertEqual(
            [transcript.transcript_id for transcript in bank],
            ["transcript_01", "transcript_02"],
        )
        self.assertEqual(bank.transcripts[0].filename, "transcript_01.txt")
        self.assertEqual(bank.transcripts[0].text, "First transcript")

    def test_rejects_empty_files_folders_and_duplicate_ids(self):
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            with self.assertRaisesRegex(ValueError, "no .txt"):
                TranscriptBank.from_directory(directory)

            (directory / "empty.txt").write_text("  \n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty"):
                TranscriptBank.from_directory(directory)

        transcript = Transcript("T1", "Text", "T1.txt")
        with self.assertRaisesRegex(ValueError, "unique"):
            TranscriptBank((transcript, transcript))


class ItemBankTests(TestCase):
    def test_reads_items_in_csv_order(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "items.csv"
            path.write_text(
                "item_id,prompt,min_value,max_value,scoring_values\n"
                "I1,Rate mood,0,100,\n"
                'I2,Rate worry,1,5,"1 = Never | 2 = Rarely | '
                '3 = Sometimes | 4 = Often | 5 = Always"\n'
                'I3,Helpful support,,,"Yes | No"\n',
                encoding="utf-8",
            )
            bank = ItemBank.from_csv(path)

        self.assertEqual([item.item_id for item in bank], ["I1", "I2", "I3"])
        self.assertEqual(bank.items[0].prompt, "Rate mood")
        self.assertEqual(bank.items[1].min_value, 1)
        self.assertEqual(bank.items[1].max_value, 5)
        self.assertEqual(
            bank.items[0].scoring_guide,
            "Any number in the allowed range.",
        )
        self.assertEqual(bank.items[1].value_labels[0], (1, "Never"))
        self.assertIn("5 = Always", bank.items[1].scoring_guide)
        self.assertIsNone(bank.items[2].min_value)
        self.assertEqual(bank.items[2].acceptable_responses, ("Yes", "No"))
        self.assertEqual(bank.items[2].allowed_values, ("Yes", "No"))
        self.assertIn("exactly one", bank.items[2].scoring_guide)
        self.assertNotIn("Numeric range", bank.items[2].response_requirements)
        self.assertIn(
            "Numeric range: 1 to 5.",
            bank.items[1].response_requirements,
        )

    def test_rejects_missing_blank_or_duplicate_items(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "items.csv"

            path.write_text(
                "wrong,prompt,min_value,max_value\nI1,Rate mood,0,100\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing columns"):
                ItemBank.from_csv(path)

            path.write_text(
                "item_id,prompt,min_value,max_value\nI1,,0,100\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "blank prompt"):
                ItemBank.from_csv(path)

        item = Item("I1", "Rate mood", 0, 100)
        with self.assertRaisesRegex(ValueError, "unique"):
            ItemBank((item, item))

        with self.assertRaisesRegex(ValueError, "less than"):
            Item("I1", "Rate mood", 100, 0)

        with self.assertRaisesRegex(ValueError, "start at min_value"):
            Item("I1", "Rate mood", 0, 3, "1 = Low | 3 = High")

        with self.assertRaisesRegex(ValueError, "unique and increasing"):
            Item("I1", "Rate mood", 0, 3, "0 = Low | 0 = Again | 3 = High")

        with self.assertRaisesRegex(ValueError, "both be set or both be blank"):
            Item("I1", "Rate mood", 0, None)

        with self.assertRaisesRegex(ValueError, "must define text"):
            Item("I1", "Rate mood", None, None)

        with self.assertRaisesRegex(ValueError, "require blank"):
            Item("I1", "Rate mood", 0, 1, "Yes | No")

        with self.assertRaisesRegex(ValueError, "cannot mix"):
            Item("I1", "Rate mood", None, None, "0 = No | Yes")

        with self.assertRaisesRegex(ValueError, "must be unique"):
            Item("I1", "Rate mood", None, None, "Yes | Yes")
