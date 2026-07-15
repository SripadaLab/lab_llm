"""Configuration: API key and model, loaded from the environment.

Keys never live in code. Set them in your shell or a local `.env`
(copy `.env.example` to `.env`). `.env` is gitignored.
"""
from __future__ import annotations

import os
from functools import lru_cache

DEFAULT_MODEL = "gpt-5.4-mini"


def _load_dotenv() -> None:
    """Load a local .env if python-dotenv is available (it's a dependency)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def get_model() -> str:
    """The model to use, from OPENAI_MODEL or the default."""
    return os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)


@lru_cache(maxsize=1)
def get_client():
    """Return a cached OpenAI client. Reads OPENAI_API_KEY from the environment."""
    _load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export OPENAI_API_KEY in your shell."
        )
    from openai import OpenAI

    return OpenAI()
