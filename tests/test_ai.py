import httpx
import openai
import pytest

from postprocessing.ai import (
    AIClient,
    AIError,
    chat_completion_options,
    parse_json_object,
)
from postprocessing.config import Settings


def settings(effort="none"):
    return Settings(
        paperless_url="http://paperless.test",
        paperless_token="t",
        openai_api_key="k",
        openai_model="gpt-6-luna",
        reasoning_effort=effort,
    )


class FakeOpenAI:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error

        class Message:
            content = self.content

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()


def test_options_send_temperature_only_without_reasoning():
    assert chat_completion_options(settings(), 0.2) == {
        "model": "gpt-6-luna",
        "reasoning_effort": "none",
        "temperature": 0.2,
    }
    assert chat_completion_options(settings("low"), 0.2) == {
        "model": "gpt-6-luna",
        "reasoning_effort": "low",
    }


@pytest.mark.parametrize(
    "text",
    ['{"a": 1}', 'Sure! {"a": 1} done', '```json\n{"a": 1}\n```'],
)
def test_parse_json_object_accepts_wrapped_json(text):
    assert parse_json_object(text) == {"a": 1}


@pytest.mark.parametrize("text", ["", "no json here", "[1, 2]", "{broken"])
def test_parse_json_object_rejects_non_objects(text):
    with pytest.raises(AIError):
        parse_json_object(text)


def test_ask_json_sends_settings_and_messages():
    fake = FakeOpenAI('{"status": "no_match"}')
    ai = AIClient(settings(), client=fake)

    assert ai.ask_json("system", "prompt") == {"status": "no_match"}
    call = fake.calls[0]
    assert call["model"] == "gpt-6-luna"
    assert call["reasoning_effort"] == "none"
    assert call["temperature"] == 0.2
    assert call["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "prompt"},
    ]
    assert "response_format" not in call


def test_ask_json_sends_a_strict_schema():
    fake = FakeOpenAI('{"status": "no_match"}')
    ai = AIClient(settings(), client=fake)
    schema = {"name": "reply", "schema": {"type": "object"}}

    ai.ask_json("system", "prompt", schema=schema)

    assert fake.calls[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "reply", "schema": {"type": "object"}, "strict": True},
    }


def test_ask_json_wraps_api_errors():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    error = openai.NotFoundError(
        "model_not_found", response=httpx.Response(404, request=request), body=None
    )
    ai = AIClient(settings(), client=FakeOpenAI(error=error))

    with pytest.raises(AIError, match="OpenAI request failed"):
        ai.ask_json("system", "prompt")


def test_ask_json_rejects_non_json_reply():
    ai = AIClient(settings(), client=FakeOpenAI("I can't help with that."))

    with pytest.raises(AIError):
        ai.ask_json("system", "prompt")
