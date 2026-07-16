"""The one-call helper: send a prompt, get a clean result back.

`call_llm()` mirrors the live-run cells on the workshop site, so code that
runs on the site behaves the same when you run it locally.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .config import get_client, get_model
from .errors import LLMResponseError


@dataclass
class Usage:
    """Token counts for one call, when the API reports them."""

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


@dataclass
class LLMResult:
    """The full response, plus convenient access to text and token usage."""

    text: str
    response: Any = field(repr=False)
    model: Optional[str] = None
    usage: Optional[Usage] = None
    response_id: Optional[str] = None
    status: Optional[str] = None


def _read_usage(response) -> Optional[Usage]:
    """Pull token counts off the response, if the API returned any."""
    raw = getattr(response, "usage", None)
    if not raw:
        return None
    return Usage(
        input_tokens=getattr(raw, "input_tokens", None),
        output_tokens=getattr(raw, "output_tokens", None),
        total_tokens=getattr(raw, "total_tokens", None),
    )


def call_llm(
    prompt: str,
    *,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
) -> LLMResult:
    """Send `prompt` to the model and return the reply.

    prompt             the user input
    instructions       optional system-style guidance
    model              override the default model
    max_output_tokens  cap the response length

    Example:
        result = call_llm("Why is the sky blue?", instructions="Be concise.")
        print(result.text)

    Raises:
        ValueError: The prompt is empty or max_output_tokens is invalid.
        LLMResponseError: The API returned a non-completed response.

    OpenAI SDK exceptions are not wrapped.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if max_output_tokens is not None and (
        isinstance(max_output_tokens, bool)
        or not isinstance(max_output_tokens, int)
        or max_output_tokens <= 0
    ):
        raise ValueError("max_output_tokens must be a positive integer")

    # Build the request, adding optional fields only when set.
    kwargs: dict = {"model": model or get_model(), "input": prompt}
    if instructions is not None:
        kwargs["instructions"] = instructions
    if max_output_tokens is not None:
        kwargs["max_output_tokens"] = max_output_tokens

    response = get_client().responses.create(**kwargs)

    if getattr(response, "status", None) != "completed":
        raise LLMResponseError(response)

    return LLMResult(
        text=response.output_text,
        response=response,
        model=getattr(response, "model", None),
        usage=_read_usage(response),
        response_id=getattr(response, "id", None),
        status=getattr(response, "status", None),
    )
