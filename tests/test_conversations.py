"""Tests for the small public conversation helper."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from lab_llm import Conversation, LLMResponseError


class FakeResponses:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


class ConversationTests(TestCase):
    def test_conversation_creation_errors_are_not_hidden(self):
        error = RuntimeError("Conversations unavailable")
        client = SimpleNamespace(
            conversations=SimpleNamespace(create=Mock(side_effect=error))
        )

        with patch("lab_llm.conversations.get_client", return_value=client):
            with self.assertRaises(RuntimeError) as caught:
                Conversation(model="test-model")

        self.assertIs(caught.exception, error)

    def test_reuses_one_conversation_and_instructions_across_turns(self):
        first = SimpleNamespace(
            id="resp_first",
            output_text="First reply",
            model="test-model",
            status="completed",
            usage=None,
        )
        second = SimpleNamespace(
            id="resp_second",
            output_text="Second reply",
            model="test-model",
            status="completed",
            usage=None,
        )
        responses = FakeResponses([first, second])
        conversations = SimpleNamespace(
            create=Mock(return_value=SimpleNamespace(id="conv_test"))
        )
        client = SimpleNamespace(
            conversations=conversations,
            responses=responses,
        )

        with (
            patch("lab_llm.conversations.get_client", return_value=client),
            patch("lab_llm.conversations.get_model", return_value="test-model"),
        ):
            chat = Conversation(instructions="Be brief.")
            first_result = chat.send("First turn")
            second_result = chat.send("Follow-up")

        self.assertEqual(chat.conversation_id, "conv_test")
        conversations.create.assert_called_once_with()
        self.assertIs(first_result.response, first)
        self.assertEqual(second_result.text, "Second reply")
        self.assertEqual(
            responses.calls,
            [
                {
                    "model": "test-model",
                    "conversation": "conv_test",
                    "input": "First turn",
                    "instructions": "Be brief.",
                },
                {
                    "model": "test-model",
                    "conversation": "conv_test",
                    "input": "Follow-up",
                    "instructions": "Be brief.",
                },
            ],
        )

    def test_omits_unsupplied_instructions_and_uses_model_override(self):
        response = SimpleNamespace(
            id="resp_test",
            output_text="Done",
            model="chosen-model",
            status="completed",
            usage=None,
        )
        responses = FakeResponses([response])
        client = SimpleNamespace(
            conversations=SimpleNamespace(
                create=lambda: SimpleNamespace(id="conv_test")
            ),
            responses=responses,
        )

        with (
            patch("lab_llm.conversations.get_client", return_value=client),
            patch("lab_llm.conversations.get_model") as get_model,
        ):
            Conversation(model="chosen-model").send("Hello")

        get_model.assert_not_called()
        self.assertEqual(
            responses.calls[0],
            {
                "model": "chosen-model",
                "conversation": "conv_test",
                "input": "Hello",
            },
        )

    def test_rejects_invalid_turns_before_creating_a_response(self):
        responses = FakeResponses()
        client = SimpleNamespace(
            conversations=SimpleNamespace(
                create=lambda: SimpleNamespace(id="conv_test")
            ),
            responses=responses,
        )

        with patch("lab_llm.conversations.get_client", return_value=client):
            chat = Conversation(model="test-model")

        for prompt in ("", "   ", None):
            with self.subTest(prompt=prompt):
                with self.assertRaisesRegex(ValueError, "non-empty string"):
                    chat.send(prompt)

        self.assertEqual(responses.calls, [])

    def test_incomplete_response_fails_closed(self):
        response = SimpleNamespace(
            id="resp_incomplete",
            status="incomplete",
            error=None,
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        )
        client = SimpleNamespace(
            conversations=SimpleNamespace(
                create=lambda: SimpleNamespace(id="conv_test")
            ),
            responses=FakeResponses([response]),
        )

        with patch("lab_llm.conversations.get_client", return_value=client):
            chat = Conversation(model="test-model")

        with self.assertRaisesRegex(
            LLMResponseError, "max_output_tokens"
        ) as caught:
            chat.send("Hello")

        self.assertIs(caught.exception.response, response)

    def test_sdk_errors_are_not_hidden(self):
        error = RuntimeError("API unavailable")
        client = SimpleNamespace(
            conversations=SimpleNamespace(
                create=lambda: SimpleNamespace(id="conv_test")
            ),
            responses=FakeResponses(error=error),
        )

        with patch("lab_llm.conversations.get_client", return_value=client):
            chat = Conversation(model="test-model")

        with self.assertRaises(RuntimeError) as caught:
            chat.send("Hello")

        self.assertIs(caught.exception, error)
