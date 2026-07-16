"""API client and default model, loaded from the environment.

Your key never lives in code. Set it in your shell or a local `.env`
(copy `.env.example` to `.env`). `.env` is gitignored.
"""
from __future__ import annotations

import os
from functools import lru_cache
from math import isfinite

from .errors import ConfigurationError


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
        raise ConfigurationError(
            "DEFAULT_MODEL is not set. Copy .env.example to .env (it sets one), "
            "or export DEFAULT_MODEL in your shell."
        )
    return model


def _optional_positive_float(name: str) -> float | None:
    """Read an optional positive number from the environment."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a positive number.") from exc
    if not isfinite(value) or value <= 0:
        raise ConfigurationError(f"{name} must be a positive number.")
    return value


def _optional_nonnegative_int(name: str) -> int | None:
    """Read an optional non-negative integer from the environment."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a non-negative integer.") from exc
    if value < 0:
        raise ConfigurationError(f"{name} must be a non-negative integer.")
    return value


@lru_cache(maxsize=4)
def _build_client(
    api_key: str,
    base_url: str | None,
    timeout: float | None,
    max_retries: int | None,
):
    """Build and cache a client for one exact configuration."""
    # Imported here so the package loads even before `openai` is installed.
    from openai import OpenAI

    kwargs = {"api_key": api_key, "base_url": base_url}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if max_retries is not None:
        kwargs["max_retries"] = max_retries
    return OpenAI(**kwargs)


def get_client():
    """Return an OpenAI client for the current environment configuration."""
    _load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ConfigurationError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export OPENAI_API_KEY in your shell."
        )

    base_url = os.environ.get("OPENAI_BASE_URL") or None
    timeout = _optional_positive_float("OPENAI_TIMEOUT")
    max_retries = _optional_nonnegative_int("OPENAI_MAX_RETRIES")
    return _build_client(api_key, base_url, timeout, max_retries)
