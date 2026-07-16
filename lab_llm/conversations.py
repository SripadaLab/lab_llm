"""Small wrappers for multi-turn model conversations."""
from __future__ import annotations

from typing import Optional

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
        conversation = self._client.conversations.create()
        self.conversation_id = conversation.id

    def send(self, prompt: str) -> LLMResult:
        """Send one turn and return the reply with the full response."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        kwargs: dict = {
            "model": self.model,
            "conversation": self.conversation_id,
            "input": prompt,
        }
        if self.instructions is not None:
            kwargs["instructions"] = self.instructions

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
