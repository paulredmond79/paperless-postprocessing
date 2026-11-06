import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import postprocess  # noqa: E402


@pytest.fixture
def document(monkeypatch):
    """Stubs every Paperless call that postprocess.main makes before OpenAI."""
    monkeypatch.setattr(
        postprocess,
        "fetch_document_details",
        lambda doc_id: {"tags": [3], "correspondent": None},
    )
    monkeypatch.setattr(postprocess, "fetch_ocr_data", lambda *a: "OCR text")
    monkeypatch.setattr(postprocess, "fetch_correspondents", lambda: {})
    added = []
    monkeypatch.setattr(
        postprocess, "add_tag_to_document", lambda doc_id, tag_id: added.append(tag_id)
    )
    monkeypatch.setattr(postprocess, "fetch_or_create_tag", lambda *a: 9)

    def fail(*args):
        raise AssertionError("must not create or assign a correspondent")

    monkeypatch.setattr(postprocess, "create_correspondent", fail)
    monkeypatch.setattr(postprocess, "update_document_correspondent", fail)
    return added


def test_no_match_adds_unable_to_determine_tag(monkeypatch, document):
    monkeypatch.setattr(
        postprocess,
        "determine_correspondent_with_openai",
        lambda *a: {"status": "no_match", "reason": "unclear"},
    )

    postprocess.main(1)

    assert document == [9]


def test_unclear_phrase_is_treated_as_no_match(monkeypatch, document):
    monkeypatch.setattr(
        postprocess,
        "determine_correspondent_with_openai",
        lambda *a: {
            "status": "suggest_new",
            "correspondent": "The OCR text does not provide a clear correspondent name.",
        },
    )

    postprocess.main(1)

    assert document == [9]


def test_unable_to_determine_tag_not_added_twice(monkeypatch, document):
    monkeypatch.setattr(postprocess, "fetch_or_create_tag", lambda *a: 3)
    monkeypatch.setattr(
        postprocess,
        "determine_correspondent_with_openai",
        lambda *a: {"status": "no_match"},
    )

    postprocess.main(1)

    assert document == []


def test_fetch_tags_follows_pagination(monkeypatch):
    postprocess.paperless_url = "http://api"
    pages = {
        "http://api/api/tags/": {
            "results": [{"id": 1, "name": "Inbox"}],
            "next": "http://api/api/tags/?page=2",
        },
        "http://api/api/tags/?page=2": {
            "results": [{"id": 5, "name": "gpt-correspondent"}],
            "next": None,
        },
    }

    class Resp:
        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            pass

        def json(self):
            return pages[self.url]

    monkeypatch.setattr(
        postprocess.requests, "get", lambda url, headers=None: Resp(url)
    )

    tags = postprocess.fetch_tags()

    assert set(tags) == {"inbox", "gpt-correspondent"}
    assert tags["gpt-correspondent"]["id"] == 5
