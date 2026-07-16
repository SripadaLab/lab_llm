"""Tests for environment configuration and client reuse."""

import os
import sys
from types import ModuleType
from unittest import TestCase
from unittest.mock import patch

from lab_llm import config
from lab_llm.errors import ConfigurationError


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
            with self.assertRaisesRegex(
                ConfigurationError, "OPENAI_API_KEY is not set"
            ):
                config.get_client()

    def test_missing_default_model_has_a_clear_error(self):
        with (
            patch.object(config, "_load_dotenv"),
            patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaisesRegex(
                ConfigurationError, "DEFAULT_MODEL is not set"
            ):
                config.get_model()

    def test_client_is_reused_until_configuration_changes(self):
        built = []

        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.api_key = kwargs["api_key"]
                self.base_url = kwargs["base_url"]
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

    def test_optional_timeout_and_retries_are_passed_to_client(self):
        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        fake_openai = ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAI

        with (
            patch.object(config, "_load_dotenv"),
            patch.dict(sys.modules, {"openai": fake_openai}),
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_TIMEOUT": "45.5",
                    "OPENAI_MAX_RETRIES": "3",
                },
                clear=True,
            ),
        ):
            client = config.get_client()

        self.assertEqual(client.kwargs["timeout"], 45.5)
        self.assertEqual(client.kwargs["max_retries"], 3)

    def test_sdk_defaults_are_used_when_optional_settings_are_absent(self):
        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        fake_openai = ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAI

        with (
            patch.object(config, "_load_dotenv"),
            patch.dict(sys.modules, {"openai": fake_openai}),
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True),
        ):
            client = config.get_client()

        self.assertNotIn("timeout", client.kwargs)
        self.assertNotIn("max_retries", client.kwargs)

    def test_invalid_timeout_and_retry_settings_have_clear_errors(self):
        cases = (
            ("OPENAI_TIMEOUT", "zero", "positive number"),
            ("OPENAI_TIMEOUT", "0", "positive number"),
            ("OPENAI_TIMEOUT", "nan", "positive number"),
            ("OPENAI_MAX_RETRIES", "1.5", "non-negative integer"),
            ("OPENAI_MAX_RETRIES", "-1", "non-negative integer"),
        )
        for name, value, message in cases:
            with self.subTest(name=name, value=value):
                with (
                    patch.object(config, "_load_dotenv"),
                    patch.dict(
                        os.environ,
                        {"OPENAI_API_KEY": "test-key", name: value},
                        clear=True,
                    ),
                ):
                    with self.assertRaisesRegex(ConfigurationError, message):
                        config.get_client()
