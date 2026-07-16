"""lab_llm: a small, reusable toolkit for LLM analysis in research labs.

Start with `call_llm` for one call. Use `Conversation` or
`StatelessConversation` for connected turns. Use `run_jobs` for independent,
resumable calls. Later modules add structured outputs and workflow helpers.
"""
from .calls import LLMResult, Usage, call_llm
from .conversations import Conversation, StatelessConversation
from .errors import ConfigurationError, LabLLMError, LLMResponseError
from .files import delete_file, temporary_file, upload_file
from .jobs import LLMJob, run_jobs
from .tools import code_interpreter_tool, web_search_tool

__all__ = [
    "call_llm",
    "Conversation",
    "StatelessConversation",
    "LLMResult",
    "Usage",
    "LabLLMError",
    "ConfigurationError",
    "LLMResponseError",
    "upload_file",
    "delete_file",
    "temporary_file",
    "web_search_tool",
    "code_interpreter_tool",
    "LLMJob",
    "run_jobs",
]
__version__ = "0.1.0"
