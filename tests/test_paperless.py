import json as jsonlib

import pytest
import requests

from postprocessing.paperless import PaperlessClient, PaperlessError, tag_ids

BASE = "http://paperless.test"


class FakeResponse:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data
        self.text = jsonlib.dumps(data) if data is not None else ""
        self.content = self.text.encode()

    def json(self):
        return self._data


class FakeSession:
    """Answers requests from a {(method, url): response or [responses]} map."""

    def __init__(self, routes):
        self.routes = routes
        self.headers = {}
        self.calls = []

    def request(self, method, url, timeout=None, params=None, json=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "timeout": timeout,
                "params": params,
                "json": json,
            }
        )
        response = self.routes[(method, url)]
        if isinstance(response, list):
            response = response.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def client(routes):
    session = FakeSession(routes)
    return PaperlessClient(BASE, "secret-token", session=session), session


def test_sets_auth_header_and_timeout():
    paperless, session = client(
        {("GET", f"{BASE}/api/documents/1/"): FakeResponse(data={"id": 1})}
    )

    assert paperless.get_document(1) == {"id": 1}
    assert session.headers["Authorization"] == "Token secret-token"
    assert session.calls[0]["timeout"] == 30


def test_list_all_follows_next_and_sends_params_once():
    page2 = f"{BASE}/api/tags/?page=2&page_size=100"
    paperless, session = client(
        {
            ("GET", f"{BASE}/api/tags/"): FakeResponse(
                data={"results": [{"id": 1, "name": "Inbox"}], "next": page2}
            ),
            ("GET", page2): FakeResponse(
                data={"results": [{"id": 5, "name": "gpt-correspondent"}], "next": None}
            ),
        }
    )

    assert [t["id"] for t in paperless.list_all("tags/")] == [1, 5]
    assert session.calls[0]["params"] == {"page_size": 100}
    assert session.calls[1]["params"] is None


def test_list_all_stops_on_repeated_next():
    url = f"{BASE}/api/tags/"
    paperless, _ = client(
        {("GET", url): [FakeResponse(data={"results": [{"id": 1}], "next": url})]}
    )

    assert paperless.list_all("tags/") == [{"id": 1}]


def test_http_error_includes_paperless_message():
    paperless, _ = client(
        {
            ("PATCH", f"{BASE}/api/documents/1/"): FakeResponse(
                400, {"custom_fields": ["Ensure this value has at most 128 characters"]}
            )
        }
    )

    with pytest.raises(PaperlessError, match="HTTP 400.*at most 128 characters"):
        paperless.update_document(1, {"title": "x"})


def test_connection_error_becomes_paperless_error():
    paperless, _ = client(
        {("GET", f"{BASE}/api/documents/1/"): requests.ConnectionError("refused")}
    )

    with pytest.raises(PaperlessError, match="refused"):
        paperless.get_document(1)


def test_get_or_create_tag_finds_existing_case_insensitively():
    paperless, session = client(
        {
            ("GET", f"{BASE}/api/tags/"): FakeResponse(
                data={"results": [{"id": 5, "name": "GPT-Correspondent"}], "next": None}
            )
        }
    )

    assert paperless.get_or_create_tag("gpt-correspondent")["id"] == 5
    assert all(call["method"] == "GET" for call in session.calls)


def test_get_or_create_correspondent_creates_when_missing():
    paperless, session = client(
        {
            ("GET", f"{BASE}/api/correspondents/"): FakeResponse(
                data={"results": [], "next": None}
            ),
            ("POST", f"{BASE}/api/correspondents/"): FakeResponse(
                201, {"id": 9, "name": "ESB Networks"}
            ),
        }
    )

    assert paperless.get_or_create_correspondent("ESB Networks")["id"] == 9
    assert session.calls[-1]["json"] == {"name": "ESB Networks"}


def test_get_or_create_recovers_when_created_concurrently():
    tags = f"{BASE}/api/tags/"
    paperless, _ = client(
        {
            ("GET", tags): [
                FakeResponse(data={"results": [], "next": None}),
                FakeResponse(
                    data={"results": [{"id": 7, "name": "new"}], "next": None}
                ),
            ],
            ("POST", tags): FakeResponse(400, {"name": ["already exists"]}),
        }
    )

    assert paperless.get_or_create_tag("new")["id"] == 7


def test_add_tags_keeps_existing_tags():
    paperless, session = client(
        {("PATCH", f"{BASE}/api/documents/1/"): FakeResponse(data={"id": 1})}
    )

    assert paperless.add_tags(1, [5], current_tag_ids={2, 3}) is True
    assert session.calls[0]["json"] == {"tags": [2, 3, 5]}


def test_add_tags_skips_update_when_already_tagged():
    paperless, session = client({})

    assert paperless.add_tags(1, [5], current_tag_ids={5}) is False
    assert session.calls == []


def test_tag_ids_accepts_ints_and_dicts():
    assert tag_ids({"tags": [1, {"id": 2}, {"name": "no id"}]}) == {1, 2}
    assert tag_ids({}) == set()
