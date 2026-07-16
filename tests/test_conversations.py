"""Tests for the small public conversation helper."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from lab_llm import Conversation, LLMResponseError, StatelessConversation


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

    def test_delete_removes_the_conversation(self):
        deleted = Mock(return_value=SimpleNamespace(deleted=True))
        conversations = SimpleNamespace(
            create=Mock(return_value=SimpleNamespace(id="conv_test")),
            delete=deleted,
        )
        client = SimpleNamespace(conversations=conversations, responses=FakeResponses([]))

        with (
            patch("lab_llm.conversations.get_client", return_value=client),
            patch("lab_llm.conversations.get_model", return_value="test-model"),
        ):
            chat = Conversation()
            chat.delete()

        deleted.assert_called_once_with("conv_test")

    def test_context_manager_deletes_after_an_error(self):
        deleted = Mock(return_value=SimpleNamespace(deleted=True))
        client = SimpleNamespace(
            conversations=SimpleNamespace(
                create=Mock(return_value=SimpleNamespace(id="conv_test")),
                delete=deleted,
            ),
            responses=FakeResponses([]),
        )

        with patch("lab_llm.conversations.get_client", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "model failed"):
                with Conversation(model="test-model") as chat:
                    self.assertEqual(chat.conversation_id, "conv_test")
                    raise RuntimeError("model failed")

        deleted.assert_called_once_with("conv_test")

    def test_delete_is_safe_inside_a_context_manager(self):
        deleted = Mock(return_value=SimpleNamespace(deleted=True))
        client = SimpleNamespace(
            conversations=SimpleNamespace(
                create=Mock(return_value=SimpleNamespace(id="conv_test")),
                delete=deleted,
            ),
            responses=FakeResponses([]),
        )

        with patch("lab_llm.conversations.get_client", return_value=client):
            with Conversation(model="test-model") as chat:
                chat.delete()

        deleted.assert_called_once_with("conv_test")

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

    def test_sends_a_file_and_tools_when_supplied(self):
        response = SimpleNamespace(
            id="resp_test",
            output_text="Done",
            model="test-model",
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
        tools = [{"type": "web_search"}]

        with patch("lab_llm.conversations.get_client", return_value=client):
            Conversation(model="test-model").send(
                "Read this file.",
                file_id="file_test",
                tools=tools,
            )

        self.assertEqual(
            responses.calls[0],
            {
                "model": "test-model",
                "conversation": "conv_test",
                "input": [{
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": "file_test"},
                        {"type": "input_text", "text": "Read this file."},
                    ],
                }],
                "tools": tools,
            },
        )

    def test_sends_multiple_files_in_order(self):
        response = SimpleNamespace(
            id="resp_test",
            output_text="Done",
            model="test-model",
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

        with patch("lab_llm.conversations.get_client", return_value=client):
            Conversation(model="test-model").send(
                "Rate these.",
                file_ids=["file_a", "file_b"],
            )

        self.assertEqual(
            responses.calls[0]["input"],
            [{
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": "file_a"},
                    {"type": "input_file", "file_id": "file_b"},
                    {"type": "input_text", "text": "Rate these."},
                ],
            }],
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

        for file_id in ("", "   "):
            with self.subTest(file_id=file_id):
                with self.assertRaisesRegex(ValueError, "file_id"):
                    chat.send("Hello", file_id=file_id)

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


class StatelessConversationTests(TestCase):
    def test_replays_complete_history_without_provider_state(self):
        reasoning = SimpleNamespace(type="reasoning")
        first_message = SimpleNamespace(type="message")
        second_message = SimpleNamespace(type="message")
        first = SimpleNamespace(
            id="resp_first",
            output_text="First reply",
            output=[reasoning, first_message],
            model="test-model",
            status="completed",
            usage=None,
        )
        second = SimpleNamespace(
            id="resp_second",
            output_text="Second reply",
            output=[second_message],
            model="test-model",
            status="completed",
            usage=None,
        )
        responses = FakeResponses([first, second])
        client = SimpleNamespace(responses=responses)

        with patch("lab_llm.conversations.get_client", return_value=client):
            chat = StatelessConversation(
                model="test-model",
                instructions="Be brief.",
            )
            chat.send("First turn")
            result = chat.send("Follow-up")

        first_user = {"role": "user", "content": "First turn"}
        second_user = {"role": "user", "content": "Follow-up"}
        self.assertEqual(
            responses.calls,
            [
                {
                    "model": "test-model",
                    "input": [first_user],
                    "store": False,
                    "instructions": "Be brief.",
                },
                {
                    "model": "test-model",
                    "input": [
                        first_user,
                        reasoning,
                        first_message,
                        second_user,
                    ],
                    "store": False,
                    "instructions": "Be brief.",
                },
            ],
        )
        self.assertEqual(
            chat.history,
            [first_user, reasoning, first_message, second_user, second_message],
        )
        self.assertEqual(result.text, "Second reply")

    def test_failed_turn_does_not_change_local_history(self):
        response = SimpleNamespace(
            id="resp_incomplete",
            status="incomplete",
            error=None,
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        )
        client = SimpleNamespace(responses=FakeResponses([response]))

        with patch("lab_llm.conversations.get_client", return_value=client):
            chat = StatelessConversation(model="test-model")

        with self.assertRaises(LLMResponseError):
            chat.send("Do not keep this turn")

        self.assertEqual(chat.history, [])

    def test_sdk_errors_are_not_hidden_or_added_to_history(self):
        error = RuntimeError("API unavailable")
        client = SimpleNamespace(responses=FakeResponses(error=error))

        with patch("lab_llm.conversations.get_client", return_value=client):
            chat = StatelessConversation(model="test-model")

        with self.assertRaises(RuntimeError) as caught:
            chat.send("Hello")

        self.assertIs(caught.exception, error)
        self.assertEqual(chat.history, [])

    def test_rejects_invalid_turns_before_creating_a_response(self):
        responses = FakeResponses()
        client = SimpleNamespace(responses=responses)

        with patch("lab_llm.conversations.get_client", return_value=client):
            chat = StatelessConversation(model="test-model")

        for prompt in ("", "   ", None):
            with self.subTest(prompt=prompt):
                with self.assertRaisesRegex(ValueError, "non-empty string"):
                    chat.send(prompt)

        self.assertEqual(responses.calls, [])
