"""Tests for versioned structured-output contracts."""

from unittest import TestCase

from pydantic import BaseModel, ConfigDict, ValidationError

from lab_llm import OutputContract


class Score(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    score: float | None


class OutputContractTests(TestCase):
    def setUp(self):
        self.contract = OutputContract(
            name="score",
            version="1",
            output_type=Score,
        )

    def test_builds_a_versioned_strict_output_format(self):
        self.assertEqual(self.contract.contract_id, "score@1")

        output_format = self.contract.output_format
        self.assertEqual(output_format["type"], "json_schema")
        self.assertEqual(output_format["name"], "score_v1")
        self.assertTrue(output_format["strict"])
        self.assertEqual(
            output_format["schema"]["additionalProperties"],
            False,
        )
        self.assertEqual(output_format["schema"]["required"], ["score"])

    def test_returns_the_declared_python_type(self):
        parsed = self.contract.parse(
            '{"score": 3}',
        )

        self.assertIsInstance(parsed, Score)
        self.assertEqual(parsed.score, 3)

    def test_rejects_json_that_does_not_match_the_type(self):
        for text in ("", "not json", '{"score": 2, "extra": true}'):
            with self.subTest(text=text):
                with self.assertRaises(ValidationError):
                    self.contract.parse(text)

    def test_allows_an_intentional_null(self):
        parsed = self.contract.parse('{"score": null}')
        self.assertIsNone(parsed.score)
