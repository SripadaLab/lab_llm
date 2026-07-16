"""Readable configurations for common hosted Responses API tools."""


def web_search_tool() -> dict:
    """Return the standard hosted web-search configuration."""
    # Pass this dictionary inside the Responses API `tools` list.
    return {"type": "web_search"}


def code_interpreter_tool() -> dict:
    """Return Code Interpreter with an automatically managed container."""
    # `auto` asks the service to manage the hosted Python container.
    return {
        "type": "code_interpreter",
        "container": {"type": "auto"},
    }
