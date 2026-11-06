"""Shared pytest set-up and in-memory fakes for Paperless and OpenAI."""

import os

import pytest

# Never load the developer's real .env during tests: real credentials must
# not reach a test.
os.environ["PAPERLESS_POSTPROCESSING_NO_DOTENV"] = "1"

from postprocessing.paperless import tag_ids  # noqa: E402

SECRET = "PPS-1234567X-SECRET-OCR-TEXT"


class FakePaperless:
    """An in-memory stand-in for PaperlessClient."""

    def __init__(self, documents=None, tags=None, correspondents=None, fields=None):
        self.documents = {d["id"]: dict(d) for d in documents or []}
        self.tags = {t["id"]: dict(t) for t in tags or []}
        self.correspondents = {c["id"]: dict(c) for c in correspondents or []}
        self.fields = list(fields or [])
        self.updates = []  # (doc_id, changes) for every update_document call
        self.deleted_correspondents = []

    def _next_id(self, table):
        return max(table, default=0) + 1

    def get_document(self, doc_id):
        return dict(self.documents[doc_id])

    def list_documents(self, params=None):
        params = params or {}
        docs = list(self.documents.values())
        if "tags__id__none" in params:
            docs = [d for d in docs if params["tags__id__none"] not in tag_ids(d)]
        if "correspondent__id" in params:
            docs = [
                d for d in docs if d.get("correspondent") == params["correspondent__id"]
            ]
        return [dict(d) for d in docs]

    def list_all(self, path, params=None):
        if path == "correspondents/":
            return [dict(c) for c in self.correspondents.values()]
        raise NotImplementedError(path)

    def update_document(self, doc_id, changes):
        self.updates.append((doc_id, changes))
        self.documents[doc_id].update(changes)

    def add_tags(self, doc_id, new_tag_ids, current_tag_ids=None):
        current = tag_ids(self.documents[doc_id])
        wanted = current | set(new_tag_ids)
        if wanted != current:
            self.update_document(doc_id, {"tags": sorted(wanted)})

    def tags_by_name(self):
        return {t["name"].lower(): t for t in self.tags.values()}

    def get_or_create_tag(self, name):
        existing = self.tags_by_name().get(name.lower())
        if existing:
            return existing
        tag = {"id": self._next_id(self.tags), "name": name}
        self.tags[tag["id"]] = tag
        return tag

    def correspondents_by_name(self):
        return {c["name"].lower(): c for c in self.correspondents.values()}

    def get_or_create_correspondent(self, name):
        existing = self.correspondents_by_name().get(name.lower())
        if existing:
            return existing
        new = {"id": self._next_id(self.correspondents), "name": name}
        self.correspondents[new["id"]] = new
        return new

    def update_correspondent(self, correspondent_id, changes):
        self.correspondents[correspondent_id].update(changes)

    def delete_correspondent(self, correspondent_id):
        self.deleted_correspondents.append(correspondent_id)
        del self.correspondents[correspondent_id]

    def custom_fields(self):
        return list(self.fields)


class FakeAI:
    """Returns queued replies (dicts) or raises queued exceptions."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []
        self.schemas = []

    def ask_json(self, system_message, prompt, temperature=0.2, schema=None):
        self.prompts.append(prompt)
        self.schemas.append(schema)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def document():
    """A typical document with OCR text, one tag and no correspondent."""
    return {
        "id": 296,
        "title": "IMG_0001",
        "content": f"Letter from ESB Networks. {SECRET}",
        "correspondent": None,
        "tags": [1],
        "custom_fields": [],
    }
