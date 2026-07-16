"""API client and default model, loaded from the environment.

Your key never lives in code. Set it in your shell or a local `.env`
(copy `.env.example` to `.env`). `.env` is gitignored.
"""
from __future__ import annotations

import os
from functools import lru_cache


def _load_dotenv() -> None:
    """Load a local `.env` into the environment, if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def get_model() -> str:
    """Return the default model, read from the DEFAULT_MODEL environment variable."""
    _load_dotenv()
    model = os.environ.get("DEFAULT_MODEL")
    if not model:
        raise RuntimeError(
            "DEFAULT_MODEL is not set. Copy .env.example to .env (it sets one), "
            "or export DEFAULT_MODEL in your shell."
        )
    return model


@lru_cache(maxsize=1)
def get_client():
    """Return a cached OpenAI client.

    Reads OPENAI_API_KEY (required) and OPENAI_BASE_URL (optional) from the
    environment or a local `.env`.
    """
    _load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export OPENAI_API_KEY in your shell."
        )
    from openai import OpenAI

    return OpenAI()
