"""lab_llm: a small, reusable toolkit for LLM analysis in research labs.

Start with `call_llm`, the one-call helper the workshop builds in Module 1.
Later modules add batch running, structured outputs, and workflow helpers.
"""
from .calls import LLMResult, Usage, call_llm
from .errors import ConfigurationError, LabLLMError, LLMResponseError

__all__ = [
    "call_llm",
    "LLMResult",
    "Usage",
    "LabLLMError",
    "ConfigurationError",
    "LLMResponseError",
]
__version__ = "0.1.0"
