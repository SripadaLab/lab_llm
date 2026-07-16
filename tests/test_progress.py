"""Tests for explicit token pricing and live progress helpers."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from lab_llm import load_token_pricing


class PricingTests(TestCase):
    def test_loads_one_model_and_service_tier(self):
        pricing = load_token_pricing(
            Path("data/model_pricing.csv"),
            "gpt-5.4-mini",
            service_tier="standard",
        )

        self.assertEqual(pricing.input_per_million, 0.75)
        self.assertEqual(pricing.cached_input_per_million, 0.075)
        self.assertEqual(pricing.output_per_million, 4.5)
        self.assertEqual(pricing.as_of, "2026-07-16")
        self.assertEqual(
            pricing.source_url,
            "https://developers.openai.com/api/docs/pricing",
        )

    def test_rejects_missing_duplicate_or_invalid_pricing(self):
        header = (
            "model,service_tier,input_per_million,cached_input_per_million,"
            "output_per_million,as_of,source_url\n"
        )
        valid_row = "test-model,standard,1,0.5,2,2026-07-16,https://example.com\n"

        with TemporaryDirectory() as directory:
            path = Path(directory) / "pricing.csv"

            path.write_text(header + valid_row, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no pricing"):
                load_token_pricing(path, "missing-model")

            path.write_text(header + valid_row + valid_row, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate pricing"):
                load_token_pricing(path, "test-model")

            path.write_text(
                header + valid_row.replace(",1,", ",not-a-number,"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "invalid pricing"):
                load_token_pricing(path, "test-model")

    def test_rejects_an_unreadable_pricing_file(self):
        with self.assertRaisesRegex(ValueError, "could not read"):
            load_token_pricing("does-not-exist.csv", "test-model")
