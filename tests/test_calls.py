"""Tests for the small public call helper."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lab_llm.calls import call_llm


class FakeResponses:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


class CallLlmTests(TestCase):
    def test_keeps_the_complete_response_and_convenient_fields(self):
        response = SimpleNamespace(
            output_text="",
            model="test-model",
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            output=[SimpleNamespace(type="message", content=["refusal details"])],
            usage=SimpleNamespace(
                input_tokens=11,
                output_tokens=7,
                total_tokens=18,
            ),
        )
        responses = FakeResponses(response=response)
        client = SimpleNamespace(responses=responses)

        with (
            patch("lab_llm.calls.get_client", return_value=client),
            patch("lab_llm.calls.get_model", return_value="default-model"),
        ):
            result = call_llm("hello")

        self.assertIs(result.response, response)
        self.assertEqual(result.response.status, "incomplete")
        self.assertEqual(result.response.output[0].content, ["refusal details"])
        self.assertEqual(result.text, "")
        self.assertEqual(result.model, "test-model")
        self.assertEqual(result.usage.total_tokens, 18)
        self.assertEqual(
            responses.kwargs,
            {"model": "default-model", "input": "hello"},
        )

    def test_forwards_only_supplied_optional_fields(self):
        response = SimpleNamespace(
            output_text="done",
            model="chosen-model",
            usage=None,
        )
        responses = FakeResponses(response=response)
        client = SimpleNamespace(responses=responses)

        with patch("lab_llm.calls.get_client", return_value=client):
            result = call_llm(
                "hello",
                instructions="Be brief.",
                model="chosen-model",
                max_output_tokens=25,
            )

        self.assertEqual(result.text, "done")
        self.assertIsNone(result.usage)
        self.assertEqual(
            responses.kwargs,
            {
                "model": "chosen-model",
                "input": "hello",
                "instructions": "Be brief.",
                "max_output_tokens": 25,
            },
        )

    def test_sdk_errors_are_not_hidden(self):
        error = RuntimeError("API unavailable")
        client = SimpleNamespace(responses=FakeResponses(error=error))

        with patch("lab_llm.calls.get_client", return_value=client):
            with self.assertRaises(RuntimeError) as caught:
                call_llm("hello", model="test-model")

        self.assertIs(caught.exception, error)
