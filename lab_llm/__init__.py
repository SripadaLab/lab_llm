"""lab_llm — a small, reusable toolkit for LLM analysis in research labs.

Start with `call_llm`, the one-call helper the workshop builds in Module 1.
Later modules add batch running, structured outputs, and workflow helpers.
"""
from .calls import LLMResult, Usage, call_llm

__all__ = ["call_llm", "LLMResult", "Usage"]
__version__ = "0.1.0"
