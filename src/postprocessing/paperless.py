"""A small client for the Paperless-ngx REST API."""

import logging

import requests
from requests.adapters import HTTPAdapter, Retry

DEFAULT_TIMEOUT = 30  # seconds per request
PAGE_SIZE = 100


class PaperlessError(Exception):
    """A Paperless API request failed."""


def tag_ids(document):
    """
    Returns a document's tag IDs as a set.

    Paperless returns tags as plain IDs or as ``{"id": ...}`` objects,
    depending on the endpoint.
    """
    ids = set()
    for tag in document.get("tags") or []:
        tag_id = tag.get("id") if isinstance(tag, dict) else tag
        if isinstance(tag_id, int):
            ids.add(tag_id)
    return ids


def _make_session():
    """Creates a session that retries rate limits and server errors."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        # Our PATCHes set absolute values, so retrying them is safe. POSTs
        # create things and are never retried, to avoid duplicates.
        allowed_methods=frozenset(["GET", "PATCH", "DELETE", "HEAD", "OPTIONS"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class PaperlessClient:
    """
    Talks to one Paperless-ngx instance.

    Every list method follows pagination, and every request has a timeout.
    Failures raise PaperlessError with Paperless's own error message, which
    names the field it rejected.
    """

    def __init__(self, base_url, token, session=None, timeout=DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or _make_session()
        self.session.headers.update(
            {"Authorization": f"Token {token}", "Accept": "application/json"}
        )

    @classmethod
    def from_settings(cls, settings):
        """Creates a client from a config.Settings."""
        return cls(settings.paperless_url, settings.paperless_token)

    # Low-level requests

    def _url(self, path):
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/api/{path.lstrip('/')}"

    def request(self, method, path, **kwargs):
        """Sends one request and returns the decoded JSON body (or None)."""
        url = self._url(path)
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as e:
            raise PaperlessError(f"{method} {url} failed: {e}") from e

        if response.status_code >= 400:
            # The body is Paperless's validation message; keep it short
            raise PaperlessError(
                f"{method} {url} failed with HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
        if not response.content:
            return None
        return response.json()

    def list_all(self, path, params=None):
        """Returns every result of a paginated list endpoint."""
        results = []
        query = {"page_size": PAGE_SIZE, **(params or {})}
        next_url = self._url(path)
        seen = set()  # stops a "next" link that points back at a seen page
        while isinstance(next_url, str) and next_url and next_url not in seen:
            seen.add(next_url)
            data = self.request("GET", next_url, params=query)
            query = None  # the "next" link already carries the query
            results.extend(data.get("results", []))
            next_url = data.get("next")
        return results

    # Documents

    def get_document(self, doc_id):
        """Returns one document, including its OCR text in ``content``."""
        return self.request("GET", f"documents/{doc_id}/")

    def list_documents(self, params=None):
        """Returns every document matching the Paperless filter ``params``."""
        return self.list_all("documents/", params)

    def update_document(self, doc_id, changes):
        """PATCHes a document with the given fields."""
        logging.debug(f"Updating document {doc_id}: {sorted(changes)}")
        return self.request("PATCH", f"documents/{doc_id}/", json=changes)

    def add_tags(self, doc_id, new_tag_ids, current_tag_ids=None):
        """
        Adds tags to a document, keeping the tags it already has.

        Pass ``current_tag_ids`` to skip re-fetching the document. Does
        nothing if every tag is already present.
        """
        if current_tag_ids is None:
            current_tag_ids = tag_ids(self.get_document(doc_id))
        wanted = set(current_tag_ids) | set(new_tag_ids)
        if wanted == set(current_tag_ids):
            return False
        self.update_document(doc_id, {"tags": sorted(wanted)})
        return True

    # Tags

    def tags_by_name(self):
        """Returns every tag, keyed by lower-case name."""
        return {tag["name"].strip().lower(): tag for tag in self.list_all("tags/")}

    def get_or_create_tag(self, name):
        """Returns the tag with this name, creating it if needed."""
        return self._get_or_create("tags/", name, self.tags_by_name)

    # Correspondents

    def correspondents_by_name(self):
        """Returns every correspondent, keyed by lower-case name."""
        return {c["name"].strip().lower(): c for c in self.list_all("correspondents/")}

    def get_or_create_correspondent(self, name):
        """Returns the correspondent with this name, creating it if needed."""
        return self._get_or_create("correspondents/", name, self.correspondents_by_name)

    def update_correspondent(self, correspondent_id, changes):
        """PATCHes a correspondent."""
        return self.request(
            "PATCH", f"correspondents/{correspondent_id}/", json=changes
        )

    def delete_correspondent(self, correspondent_id):
        """Deletes a correspondent. This can't be undone."""
        return self.request("DELETE", f"correspondents/{correspondent_id}/")

    # Custom fields

    def custom_fields(self):
        """Returns every custom field definition."""
        return self.list_all("custom_fields/")

    # Helpers

    def _get_or_create(self, path, name, fetch_by_name):
        existing = fetch_by_name().get(name.strip().lower())
        if existing:
            return existing
        kind = path.rstrip("/")[:-1]
        try:
            created = self.request("POST", path, json={"name": name})
            # Not the name: a correspondent's name can be a person's
            logging.info(f"Created {kind} {created['id']}.")
            return created
        except PaperlessError:
            # Another process may have created it a moment ago
            existing = fetch_by_name().get(name.strip().lower())
            if existing:
                return existing
            raise
