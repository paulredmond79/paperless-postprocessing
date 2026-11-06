"""Shared start-up code for the scripts in ``src/``."""

import logging

from postprocessing.ai import AIClient
from postprocessing.config import (
    ConfigError,
    Settings,
    configure_logging,
    load_env,
)
from postprocessing.paperless import PaperlessClient

# Exit codes shared by every script
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CONFIG = 2


def build_clients(require_openai=True):
    """Loads settings and returns (PaperlessClient, AIClient or None)."""
    settings = Settings.from_env(require_openai=require_openai)
    paperless = PaperlessClient.from_settings(settings)
    ai = AIClient(settings) if require_openai else None
    return paperless, ai


def run(main, argv=None):
    """
    Runs a script's ``main(argv)`` and returns its exit code.

    Loads ``.env`` and sets up logging first, and turns a missing setting
    into a clear error with exit code 2.
    """
    load_env()
    configure_logging()
    try:
        return main(argv)
    except ConfigError as e:
        logging.error(str(e))
        return EXIT_CONFIG
