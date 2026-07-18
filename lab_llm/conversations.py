"""Small wrappers for multi-turn model conversations."""
from __future__ import annotations

from typing import Any, Optional

from .calls import LLMResult
from .config import get_client, get_model
from .privacy import DeidentificationSummary, Deidentifier


class Conversation:
    """One durable conversation with shared model instructions."""

    def __init__(
        self,
        *,
        instructions: Optional[str] = None,
        model: Optional[str] = None,
        deidentifier: Optional[Deidentifier] = None,
    ):
        self.deidentifier = deidentifier
        self._instruction_privacy = None
        if instructions is not None and deidentifier is not None:
            result = deidentifier.deidentify(instructions)
            instructions = result.text
            self._instruction_privacy = result.summary
        self._client = get_client()
        self.model = model or get_model()
        self.instructions = instructions

        # The service stores turns attached to this conversation ID.
        conversation = self._client.conversations.create()
        self.conversation_id = conversation.id
        self._deleted = False
        self._delete_result = None

    def __enter__(self) -> "Conversation":
        """Use this conversation inside a cleanup-safe `with` block."""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Delete the server-side conversation when the block ends."""
        self.delete()

    def send(
        self,
        prompt: str,
        *,
        file_id: Optional[str] = None,
        file_ids: Optional[list[str]] = None,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResult:
        """Send one turn and return the reply with the full response."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        # Accept one file (file_id) or several (file_ids). Order is preserved.
        ids: list[str] = []
        if file_id is not None:
            ids.append(file_id)
        if file_ids is not None:
            ids.extend(file_ids)
        for fid in ids:
            if not isinstance(fid, str) or not fid.strip():
                raise ValueError("file_id must be a non-empty string")

        prompt_privacy = None
        if self.deidentifier is not None:
            result = self.deidentifier.deidentify(prompt)
            prompt = result.text
            prompt_privacy = result.summary

        input_value: Any = prompt
        if ids:
            # Each file plus the prompt are content items in one user message.
            content = [{"type": "input_file", "file_id": fid} for fid in ids]
            content.append({"type": "input_text", "text": prompt})
            input_value = [{"role": "user", "content": content}]

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
        privacy_summaries = [
            summary
            for summary in (self._instruction_privacy, prompt_privacy)
            if summary is not None
        ]
        return LLMResult.from_response(
            response,
            deidentification=(
                DeidentificationSummary.combine(privacy_summaries)
                if privacy_summaries
                else None
            ),
        )

    def delete(self):
        """Delete this conversation and its stored items from the service."""
        # Safe to call explicitly inside a `with` block. The block will not
        # issue a second delete when it closes.
        if not self._deleted:
            self._delete_result = self._client.conversations.delete(
                self.conversation_id
            )
            self._deleted = True
        return self._delete_result


class StatelessConversation:
    """A conversation whose complete history stays with this process."""

    def __init__(
        self,
        *,
        instructions: Optional[str] = None,
        model: Optional[str] = None,
        deidentifier: Optional[Deidentifier] = None,
    ):
        self.deidentifier = deidentifier
        self._instruction_privacy = None
        if instructions is not None and deidentifier is not None:
            result = deidentifier.deidentify(instructions)
            instructions = result.text
            self._instruction_privacy = result.summary
        self._client = get_client()
        self.model = model or get_model()
        self.instructions = instructions
        self.history: list = []

    def send(self, prompt: str) -> LLMResult:
        """Send one turn, then keep its input and output in local history."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        prompt_privacy = None
        if self.deidentifier is not None:
            result = self.deidentifier.deidentify(prompt)
            prompt = result.text
            prompt_privacy = result.summary

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
        privacy_summaries = [
            summary
            for summary in (self._instruction_privacy, prompt_privacy)
            if summary is not None
        ]
        result = LLMResult.from_response(
            response,
            deidentification=(
                DeidentificationSummary.combine(privacy_summaries)
                if privacy_summaries
                else None
            ),
        )

        # Keep every output item. Reasoning and tool context matter too.
        self.history = [*input_items, *response.output]
        return result
