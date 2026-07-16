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


@lru_cache(maxsize=4)
def _build_client(api_key: str, base_url: str | None):
    """Build and cache a client for one exact configuration."""
    # Imported here so the package loads even before `openai` is installed.
    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url)


def get_client():
    """Return an OpenAI client for the current environment configuration."""
    _load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export OPENAI_API_KEY in your shell."
        )

    base_url = os.environ.get("OPENAI_BASE_URL") or None
    return _build_client(api_key, base_url)
