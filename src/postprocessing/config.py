"""Settings from the environment and the gitignored ``.env`` file."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# <repo>/src/postprocessing/config.py -> <repo>/.env
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Set this to any value to skip loading the .env file (the test suite does).
DISABLE_DOTENV_VAR = "PAPERLESS_POSTPROCESSING_NO_DOTENV"

DEFAULT_PAPERLESS_URL = "http://localhost:8000"
DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_REASONING_EFFORT = "none"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# These libraries log request bodies (which contain OCR text) at DEBUG
QUIET_LOGGERS = ("openai", "httpx", "httpcore", "urllib3")


class ConfigError(Exception):
    """A required setting is missing."""


def load_env(env_file=None):
    """
    Loads variables from the ``.env`` file into ``os.environ``.

    Variables that are already set in the environment win over the file, so
    a Paperless container's own settings still apply. Does nothing when the
    file doesn't exist or ``PAPERLESS_POSTPROCESSING_NO_DOTENV`` is set.
    Returns True if a file was loaded.
    """
    if os.getenv(DISABLE_DOTENV_VAR):
        return False

    path = Path(env_file) if env_file else DEFAULT_ENV_FILE
    if not path.is_file():
        return False

    try:
        from dotenv import load_dotenv
    except ImportError:
        logging.warning(
            f"Found {path} but python-dotenv isn't installed, so it was not loaded. "
            "Run: pip install -r requirements.txt"
        )
        return False

    return load_dotenv(path, override=False)


def configure_logging():
    """
    Configures the root logger. The level defaults to INFO.

    Set ``LOG_LEVEL`` (DEBUG, INFO, WARNING or ERROR) to change it. An
    unknown value falls back to INFO. Call this after ``load_env()`` so a
    ``LOG_LEVEL`` in ``.env`` applies. The OpenAI and HTTP libraries stay
    at WARNING or above, because their debug output includes prompts.
    Returns the level used.
    """
    name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = logging.getLevelName(name)
    if not isinstance(level, int):
        level = logging.INFO

    logging.basicConfig(level=level, format=LOG_FORMAT)
    logging.getLogger().setLevel(level)
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(max(level, logging.WARNING))
    return level


@dataclass(frozen=True)
class Settings:
    """Everything the scripts need to talk to Paperless and OpenAI."""

    paperless_url: str
    paperless_token: str
    openai_api_key: Optional[str]
    openai_model: str
    reasoning_effort: str

    @classmethod
    def from_env(cls, require_openai=True):
        """
        Reads the settings from the environment.

        Raises ConfigError naming every missing required setting, so a
        misconfigured hook fails with a clear message instead of sending
        ``Token None`` to Paperless.
        """
        url = (os.getenv("PAPERLESS_URL") or DEFAULT_PAPERLESS_URL).strip()
        token = (os.getenv("PAPERLESS_API_TOKEN") or "").strip()
        key = (os.getenv("OPENAI_API_KEY") or "").strip()

        missing = []
        if not token:
            missing.append("PAPERLESS_API_TOKEN")
        if require_openai and not key:
            missing.append("OPENAI_API_KEY")
        if missing:
            raise ConfigError(
                f"Missing setting(s): {', '.join(missing)}. "
                "Set them in .env or in the environment."
            )

        return cls(
            paperless_url=url.rstrip("/"),
            paperless_token=token,
            openai_api_key=key or None,
            openai_model=(os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip(),
            reasoning_effort=(
                os.getenv("OPENAI_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT
            ).strip(),
        )
