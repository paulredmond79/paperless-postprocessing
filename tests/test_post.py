import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import os
import post


def test_to_snake_case_basic():
    assert post.to_snake_case("Hello World") == "hello_world"


def test_to_snake_case_special_chars():
    assert post.to_snake_case(" Example---Test! ") == "example_test"


def test_clean_fields_date_and_money():
    fields = {
        "date_field": "01.02.2023",
        "money_field": "1234,50",
        "ignored_field": "value"
    }
    field_meta = {
        "date_field": {"data_type": "date"},
        "money_field": {"data_type": "monetary"}
    }
    cleaned = post.clean_fields(fields, field_meta)
    assert cleaned == {
        "date_field": "2023-02-01",
        "money_field": "1234.5"
    }


def test_clean_fields_invalid_date():
    fields = {"date_field": "32/13/2023"}
    field_meta = {"date_field": {"data_type": "date"}}
    cleaned = post.clean_fields(fields, field_meta)
    assert cleaned == {}


class DummyChat:
    def __init__(self, content):
        self.content = content


class DummyMessage:
    def __init__(self, content):
        self.message = DummyChat(content)


class DummyChoices:
    def __init__(self, content):
        self.choices = [DummyMessage(content)]


class DummyClient:
    def __init__(self, *args, **kwargs):
        pass

    class chat:
        class completions:
            @staticmethod
            def create(*args, **kwargs):
                return DummyChoices(
                    "Random text {\"title\": \"Test Document\", \"fields\": {\"amount\": \"12.34\"}} end"
                )


def test_generate_metadata_with_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setattr(post, "OpenAI", lambda api_key=None: DummyClient())
    result = post.generate_metadata_with_openai("some ocr text", ["amount"])
    assert result == {"title": "Test Document", "fields": {"amount": "12.34"}}
