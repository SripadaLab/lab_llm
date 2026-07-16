"""Tests for the small public call helper."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lab_llm.calls import call_llm
from lab_llm.errors import LLMResponseError


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
            id="resp_test",
            output_text="",
            model="test-model",
            status="completed",
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
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.response_id, "resp_test")
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
            id="resp_test",
            output_text="done",
            model="chosen-model",
            status="completed",
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

    def test_incomplete_response_fails_closed_and_keeps_response(self):
        response = SimpleNamespace(
            id="resp_incomplete",
            status="incomplete",
            error=None,
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        )
        client = SimpleNamespace(responses=FakeResponses(response=response))

        with patch("lab_llm.calls.get_client", return_value=client):
            with self.assertRaisesRegex(
                LLMResponseError, "max_output_tokens"
            ) as caught:
                call_llm("hello", model="test-model")

        self.assertIs(caught.exception.response, response)
        self.assertEqual(caught.exception.status, "incomplete")
        self.assertEqual(caught.exception.reason, "max_output_tokens")
        self.assertEqual(caught.exception.response_id, "resp_incomplete")

    def test_failed_response_fails_closed_and_reports_api_error(self):
        response = SimpleNamespace(
            id="resp_failed",
            status="failed",
            error=SimpleNamespace(code="server_error", message="Generation failed."),
            incomplete_details=None,
        )
        client = SimpleNamespace(responses=FakeResponses(response=response))

        with patch("lab_llm.calls.get_client", return_value=client):
            with self.assertRaisesRegex(
                LLMResponseError, "Generation failed"
            ) as caught:
                call_llm("hello", model="test-model")

        self.assertIs(caught.exception.response, response)
        self.assertIs(caught.exception.error, response.error)

    def test_unexpected_response_status_fails_closed(self):
        response = SimpleNamespace(
            id="resp_queued",
            status="queued",
            error=None,
            incomplete_details=None,
        )
        client = SimpleNamespace(responses=FakeResponses(response=response))

        with patch("lab_llm.calls.get_client", return_value=client):
            with self.assertRaisesRegex(LLMResponseError, "status='queued'"):
                call_llm("hello", model="test-model")

    def test_rejects_invalid_input_before_creating_a_client(self):
        with patch("lab_llm.calls.get_client") as get_client:
            for prompt in ("", "   ", None):
                with self.subTest(prompt=prompt):
                    with self.assertRaisesRegex(ValueError, "non-empty string"):
                        call_llm(prompt, model="test-model")

            for limit in (0, -1, 1.5, True):
                with self.subTest(max_output_tokens=limit):
                    with self.assertRaisesRegex(ValueError, "positive integer"):
                        call_llm(
                            "hello",
                            model="test-model",
                            max_output_tokens=limit,
                        )

        get_client.assert_not_called()
