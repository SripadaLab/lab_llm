"""Tests for readable hosted-tool configurations."""

from unittest import TestCase

from lab_llm import code_interpreter_tool, web_search_tool


class ToolTests(TestCase):
    def test_web_search_tool(self):
        self.assertEqual(web_search_tool(), {"type": "web_search"})

    def test_code_interpreter_tool(self):
        self.assertEqual(
            code_interpreter_tool(),
            {
                "type": "code_interpreter",
                "container": {"type": "auto"},
            },
        )
