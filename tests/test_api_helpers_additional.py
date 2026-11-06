import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # noqa: E402

from utils import api_helpers  # noqa: E402
from utils.api_helpers import (  # noqa: E402
    ensure_custom_field_exists,
    fetch_correspondents,
    fetch_custom_fields,
    fetch_document_details,
    get_correspondents,
    update_document_metadata,
)

API_URL = "http://mockapi.com"
HEADERS = {"Authorization": "Token mocktoken"}


def test_fetch_correspondents_failure(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError()

    monkeypatch.setattr("requests.get", lambda *a, **k: MockResponse())
    assert fetch_correspondents(API_URL, HEADERS) == {}


def test_get_correspondents_success(monkeypatch):
    resp_data = {"results": [{"name": "Alice", "id": 42}]}

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return resp_data

    monkeypatch.setattr("requests.get", lambda *a, **k: MockResponse())
    assert get_correspondents(API_URL, HEADERS) == {"Alice": 42}


def test_get_correspondents_failure(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError()

    monkeypatch.setattr("requests.get", lambda *a, **k: MockResponse())
    assert get_correspondents(API_URL, HEADERS) == {}


def test_fetch_document_details_success(monkeypatch):
    resp_data = {"id": 1, "title": "doc"}

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return resp_data

    monkeypatch.setattr("requests.get", lambda *a, **k: MockResponse())
    assert fetch_document_details(API_URL, HEADERS, 1) == resp_data


def test_fetch_document_details_failure(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError()

    monkeypatch.setattr("requests.get", lambda *a, **k: MockResponse())
    with pytest.raises(Exception):
        fetch_document_details(API_URL, HEADERS, 1)


def test_update_document_metadata_success(monkeypatch):
    called = {}

    class MockResponse:
        def raise_for_status(self):
            pass

    def mock_patch(url, headers=None, json=None):
        called["url"] = url
        called["headers"] = headers
        called["json"] = json
        return MockResponse()

    monkeypatch.setattr("requests.patch", mock_patch)
    update_document_metadata(API_URL, HEADERS, 1, {"title": "new"})
    assert called["url"] == f"{API_URL}/api/documents/1/"
    assert called["headers"] == HEADERS
    assert called["json"] == {"title": "new"}


def test_update_document_metadata_failure(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError()

    monkeypatch.setattr("requests.patch", lambda *a, **k: MockResponse())
    with pytest.raises(Exception):
        update_document_metadata(API_URL, HEADERS, 1, {"title": "new"})


def test_fetch_custom_fields_failure(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError()

    monkeypatch.setattr("requests.get", lambda *a, **k: MockResponse())
    with pytest.raises(Exception):
        fetch_custom_fields(API_URL, HEADERS)


def test_ensure_custom_field_exists_create_success(monkeypatch):
    class MockGetResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": []}

    class MockPostResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id": 7, "name": "Field", "data_type": "string"}

    monkeypatch.setattr("requests.get", lambda *a, **k: MockGetResponse())
    monkeypatch.setattr("requests.post", lambda *a, **k: MockPostResponse())
    result = ensure_custom_field_exists(API_URL, HEADERS, "Field")
    assert result == {"id": 7, "name": "Field", "data_type": "string"}


def _paged_get(pages):
    class Resp:
        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            pass

        def json(self):
            return pages[self.url]

    return lambda url, headers=None: Resp(url)


def test_fetch_all_results_follows_next(monkeypatch):
    pages = {
        "http://api/api/tags/": {"results": [{"id": 1}], "next": "http://api/p2"},
        "http://api/p2": {"results": [{"id": 2}], "next": None},
    }
    monkeypatch.setattr(api_helpers.requests, "get", _paged_get(pages))

    assert api_helpers.fetch_all_results("http://api/api/tags/", {}) == [
        {"id": 1},
        {"id": 2},
    ]


def test_fetch_all_results_stops_on_repeated_next(monkeypatch):
    pages = {"http://api/loop": {"results": [{"id": 1}], "next": "http://api/loop"}}
    monkeypatch.setattr(api_helpers.requests, "get", _paged_get(pages))

    assert api_helpers.fetch_all_results("http://api/loop", {}) == [{"id": 1}]


def test_fetch_tags_reads_every_page(monkeypatch):
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
    monkeypatch.setattr(api_helpers.requests, "get", _paged_get(pages))

    assert api_helpers.fetch_tags("http://api", {}) == {
        "Inbox": 1,
        "gpt-correspondent": 5,
    }
