"""lab_llm: a small, reusable toolkit for LLM analysis in research labs.

Start with `call_llm` for one call. Use `Conversation` for connected turns.
Later modules add batch running, structured outputs, and workflow helpers.
"""
from .calls import LLMResult, Usage, call_llm
from .conversations import Conversation
from .errors import ConfigurationError, LabLLMError, LLMResponseError

__all__ = [
    "call_llm",
    "Conversation",
    "LLMResult",
    "Usage",
    "LabLLMError",
    "ConfigurationError",
    "LLMResponseError",
]
__version__ = "0.1.0"
