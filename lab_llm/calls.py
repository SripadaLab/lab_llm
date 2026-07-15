"""The one-call helper: send a prompt, get a clean result back.

This mirrors `call_llm()` in the workshop site's live-run cells, so code you
run on the site behaves the same when you run it locally.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import get_client, get_model


@dataclass
class Usage:
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


@dataclass
class LLMResult:
    text: str
    model: Optional[str] = None
    usage: Optional[Usage] = None


def call_llm(
    prompt: str,
    *,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
) -> LLMResult:
    """Send `prompt` to the model and return the reply as text.

    prompt            the user input
    instructions      optional system-style guidance
    model             override the default model
    max_output_tokens cap the response length
    """
    kwargs: dict = {"model": model or get_model(), "input": prompt}
    if instructions is not None:
        kwargs["instructions"] = instructions
    if max_output_tokens is not None:
        kwargs["max_output_tokens"] = max_output_tokens

    response = get_client().responses.create(**kwargs)

    raw = getattr(response, "usage", None)
    usage = (
        Usage(
            input_tokens=getattr(raw, "input_tokens", None),
            output_tokens=getattr(raw, "output_tokens", None),
            total_tokens=getattr(raw, "total_tokens", None),
        )
        if raw
        else None
    )

    return LLMResult(
        text=response.output_text,
        model=getattr(response, "model", None),
        usage=usage,
    )
