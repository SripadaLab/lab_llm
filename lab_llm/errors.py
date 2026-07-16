"""Exceptions raised by lab_llm itself.

OpenAI SDK exceptions are intentionally not wrapped. Callers can still catch
the SDK's specific authentication, rate-limit, connection, and API errors.
"""
from __future__ import annotations

from typing import Any, Optional


class LabLLMError(RuntimeError):
    """Base class for errors raised by lab_llm itself."""


class ConfigurationError(LabLLMError):
    """Invalid or missing lab_llm configuration."""


class LLMResponseError(LabLLMError):
    """The API returned a response that did not complete successfully."""

    def __init__(self, response: Any):
        self.response = response
        self.response_id: Optional[str] = getattr(response, "id", None)
        self.status: Optional[str] = getattr(response, "status", None)
        self.error = getattr(response, "error", None)

        details = getattr(response, "incomplete_details", None)
        self.reason: Optional[str] = getattr(details, "reason", None)

        explanation = self.reason or self._error_detail() or "no reason reported"
        response_label = (
            f" (response {self.response_id})" if self.response_id else ""
        )
        super().__init__(
            f"LLM response did not complete: status={self.status!r}; "
            f"{explanation}{response_label}"
        )

    def _error_detail(self) -> Optional[str]:
        if self.error is None:
            return None
        if isinstance(self.error, dict):
            return self.error.get("message") or self.error.get("code")
        return getattr(self.error, "message", None) or getattr(
            self.error, "code", None
        )
