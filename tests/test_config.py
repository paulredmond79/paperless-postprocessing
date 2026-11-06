import logging
import os
from pathlib import Path

import pytest

from postprocessing import config
from postprocessing.config import ConfigError, Settings

SETTINGS_VARS = [
    "PAPERLESS_URL",
    "PAPERLESS_API_TOKEN",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_REASONING_EFFORT",
]


@pytest.fixture
def clean_env(monkeypatch):
    for name in SETTINGS_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


# .env loading


def test_default_env_file_is_repo_root():
    assert config.DEFAULT_ENV_FILE == Path(__file__).resolve().parents[1] / ".env"


def test_tests_never_load_the_real_env_file():
    assert os.environ.get(config.DISABLE_DOTENV_VAR)


def test_load_env_reads_file_without_overriding(monkeypatch, tmp_path):
    env_file = tmp_path / "settings.env"
    env_file.write_text("PPTEST_NEW=from-file\nPPTEST_SET=from-file\n")
    monkeypatch.delenv(config.DISABLE_DOTENV_VAR)
    monkeypatch.delenv("PPTEST_NEW", raising=False)
    monkeypatch.setenv("PPTEST_SET", "from-shell")

    assert config.load_env(env_file) is True
    assert os.environ["PPTEST_NEW"] == "from-file"
    assert os.environ["PPTEST_SET"] == "from-shell"
    monkeypatch.delenv("PPTEST_NEW")


def test_load_env_missing_file(monkeypatch, tmp_path):
    monkeypatch.delenv(config.DISABLE_DOTENV_VAR)

    assert config.load_env(tmp_path / "missing.env") is False


def test_load_env_disabled(tmp_path):
    env_file = tmp_path / "settings.env"
    env_file.write_text("PPTEST_DISABLED=from-file\n")

    assert config.load_env(env_file) is False
    assert "PPTEST_DISABLED" not in os.environ


# Logging


@pytest.fixture
def restore_root_level():
    loggers = [logging.getLogger()] + [
        logging.getLogger(name) for name in config.QUIET_LOGGERS
    ]
    levels = [logger.level for logger in loggers]
    yield
    for logger, level in zip(loggers, levels):
        logger.setLevel(level)


def test_logging_defaults_to_info(monkeypatch, restore_root_level):
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    assert config.configure_logging() == logging.INFO


def test_logging_level_override(monkeypatch, restore_root_level):
    monkeypatch.setenv("LOG_LEVEL", " debug ")

    assert config.configure_logging() == logging.DEBUG


def test_debug_logging_keeps_openai_and_http_libraries_quiet(
    monkeypatch, restore_root_level
):
    # The OpenAI SDK logs request options, including the prompt, at DEBUG
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    config.configure_logging()

    for name in config.QUIET_LOGGERS:
        assert not logging.getLogger(name).isEnabledFor(logging.DEBUG)
        assert not logging.getLogger(name).isEnabledFor(logging.INFO)


def test_unknown_logging_level_falls_back_to_info(monkeypatch, restore_root_level):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    assert config.configure_logging() == logging.INFO


# Settings


def test_settings_defaults(clean_env):
    clean_env.setenv("PAPERLESS_API_TOKEN", "t")
    clean_env.setenv("OPENAI_API_KEY", "k")

    settings = Settings.from_env()

    assert settings.paperless_url == "http://localhost:8000"
    assert settings.openai_model == "gpt-6-luna"
    assert settings.reasoning_effort == "none"


def test_settings_overrides_and_trailing_slash(clean_env):
    clean_env.setenv("PAPERLESS_URL", "https://paperless.example.com/")
    clean_env.setenv("PAPERLESS_API_TOKEN", "t")
    clean_env.setenv("OPENAI_API_KEY", "k")
    clean_env.setenv("OPENAI_MODEL", "gpt-6.1-terra")
    clean_env.setenv("OPENAI_REASONING_EFFORT", "low")

    settings = Settings.from_env()

    assert settings.paperless_url == "https://paperless.example.com"
    assert settings.openai_model == "gpt-6.1-terra"
    assert settings.reasoning_effort == "low"


def test_settings_names_every_missing_value(clean_env):
    with pytest.raises(ConfigError) as exc:
        Settings.from_env()

    assert "PAPERLESS_API_TOKEN" in str(exc.value)
    assert "OPENAI_API_KEY" in str(exc.value)


def test_settings_without_openai(clean_env):
    clean_env.setenv("PAPERLESS_API_TOKEN", "t")

    settings = Settings.from_env(require_openai=False)

    assert settings.openai_api_key is None
