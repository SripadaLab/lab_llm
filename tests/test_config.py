"""Tests for environment configuration and client reuse."""

import os
import sys
from types import ModuleType
from unittest import TestCase
from unittest.mock import patch

from lab_llm import config


class ConfigTests(TestCase):
    def setUp(self):
        config._build_client.cache_clear()

    def tearDown(self):
        config._build_client.cache_clear()

    def test_missing_api_key_has_a_clear_error(self):
        with (
            patch.object(config, "_load_dotenv"),
            patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY is not set"):
                config.get_client()

    def test_missing_default_model_has_a_clear_error(self):
        with (
            patch.object(config, "_load_dotenv"),
            patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "DEFAULT_MODEL is not set"):
                config.get_model()

    def test_client_is_reused_until_configuration_changes(self):
        built = []

        class FakeOpenAI:
            def __init__(self, *, api_key, base_url):
                self.api_key = api_key
                self.base_url = base_url
                built.append(self)

        fake_openai = ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAI

        with (
            patch.object(config, "_load_dotenv"),
            patch.dict(sys.modules, {"openai": fake_openai}),
            patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "first-key", "OPENAI_BASE_URL": "https://one"},
                clear=True,
            ),
        ):
            first = config.get_client()
            same = config.get_client()
            os.environ["OPENAI_API_KEY"] = "second-key"
            os.environ["OPENAI_BASE_URL"] = "https://two"
            changed = config.get_client()

        self.assertIs(first, same)
        self.assertIsNot(first, changed)
        self.assertEqual(changed.api_key, "second-key")
        self.assertEqual(changed.base_url, "https://two")
        self.assertEqual(len(built), 2)
