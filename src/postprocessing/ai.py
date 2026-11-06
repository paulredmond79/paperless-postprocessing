"""The OpenAI wrapper: sends a prompt and returns the reply as parsed JSON."""

import json
import logging
import re

import openai


class AIError(Exception):
    """The OpenAI request failed or its reply wasn't the JSON we asked for."""


def chat_completion_options(settings, temperature=None):
    """
    Returns the model keyword arguments for ``chat.completions.create``.

    OpenAI rejects sampling parameters unless reasoning is off, so
    ``temperature`` is only sent when the reasoning effort is ``none``.
    """
    options = {
        "model": settings.openai_model,
        "reasoning_effort": settings.reasoning_effort,
    }
    if temperature is not None and settings.reasoning_effort == "none":
        options["temperature"] = temperature
    return options


def parse_json_object(text):
    """
    Parses a JSON object from a model reply.

    Accepts a bare object or one wrapped in other text (for example a code
    fence). Raises AIError if there's no object.
    """
    text = (text or "").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise AIError("The reply contained no JSON object.")
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise AIError(f"The reply's JSON is invalid: {e}") from e

    if not isinstance(value, dict):
        raise AIError("The reply's JSON is not an object.")
    return value


class AIClient:
    """Asks OpenAI questions that must be answered with a JSON object."""

    def __init__(self, settings, client=None):
        self.settings = settings
        self._client = client or openai.OpenAI(api_key=settings.openai_api_key)

    def ask_json(self, system_message, prompt, temperature=0.2, schema=None):
        """
        Sends the prompt and returns the reply as a dict.

        Pass ``schema`` (a ``{"name": ..., "schema": {...}}`` dict) to make
        OpenAI's structured outputs enforce the reply's shape. Raises AIError
        for API errors and for replies that aren't a JSON object. Never logs
        the prompt or reply: both contain document text.
        """
        options = chat_completion_options(self.settings, temperature)
        if schema:
            options["response_format"] = {
                "type": "json_schema",
                "json_schema": {**schema, "strict": True},
            }
        try:
            response = self._client.chat.completions.create(
                **options,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
            )
        except openai.OpenAIError as e:
            raise AIError(f"OpenAI request failed: {e}") from e

        content = response.choices[0].message.content or ""
        logging.debug(f"OpenAI reply received ({len(content)} characters).")
        return parse_json_object(content)
