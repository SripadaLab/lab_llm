"""Small wrappers for multi-turn model conversations."""
from __future__ import annotations

from typing import Any, Optional

from .calls import LLMResult
from .config import get_client, get_model


class Conversation:
    """One durable conversation with shared model instructions."""

    def __init__(
        self,
        *,
        instructions: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._client = get_client()
        self.model = model or get_model()
        self.instructions = instructions

        # The service stores turns attached to this conversation ID.
        conversation = self._client.conversations.create()
        self.conversation_id = conversation.id

    def send(
        self,
        prompt: str,
        *,
        file_id: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResult:
        """Send one turn and return the reply with the full response."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        if file_id is not None and (
            not isinstance(file_id, str) or not file_id.strip()
        ):
            raise ValueError("file_id must be a non-empty string")

        input_value: Any = prompt
        if file_id is not None:
            # A file and its prompt are content items in one user message.
            input_value = [{
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": file_id},
                    {"type": "input_text", "text": prompt},
                ],
            }]

        kwargs: dict = {
            "model": self.model,
            "conversation": self.conversation_id,
            "input": input_value,
        }

        # Omit unused options. Let the SDK apply its own defaults.
        if self.instructions is not None:
            kwargs["instructions"] = self.instructions
        if tools is not None:
            kwargs["tools"] = tools

        response = self._client.responses.create(**kwargs)
        return LLMResult.from_response(response)


class StatelessConversation:
    """A conversation whose complete history stays with this process."""

    def __init__(
        self,
        *,
        instructions: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._client = get_client()
        self.model = model or get_model()
        self.instructions = instructions
        self.history: list = []

    def send(self, prompt: str) -> LLMResult:
        """Send one turn, then keep its input and output in local history."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        user_message = {"role": "user", "content": prompt}
        input_items = [*self.history, user_message]
        kwargs: dict = {
            "model": self.model,
            "input": input_items,
            "store": False,
        }
        if self.instructions is not None:
            kwargs["instructions"] = self.instructions

        response = self._client.responses.create(**kwargs)
        result = LLMResult.from_response(response)

        # Keep every output item. Reasoning and tool context matter too.
        self.history = [*input_items, *response.output]
        return result
