import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # noqa: E402

# isort: off
from utils.api_helpers import (  # noqa: E402
    add_tag_to_document,
    create_correspondent,
    create_tag,
    ensure_custom_field_exists,
    fetch_correspondents,
    fetch_ocr_data,
    fetch_or_create_tag,
    fetch_tags,
)  # noqa: E402

# isort: on
from utils import api_helpers  # noqa: E402


def test_to_snake_case():
    assert api_helpers.to_snake_case("Test Field Name") == "test_field_name"


def test_fetch_custom_fields(monkeypatch):
    fake_response = {
        "results": [
            {"id": 1, "name": "Invoice Date", "data_type": "date"},
            {"id": 2, "name": "Amount Due", "data_type": "monetary"},
        ]
    }

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_response

    def fake_get(url, headers=None):
        return Resp()

    monkeypatch.setattr(api_helpers.requests, "get", fake_get)
    result = api_helpers.fetch_custom_fields("http://api", {})
    assert result == {
        "invoice_date": {"id": 1, "data_type": "date"},
        "amount_due": {"id": 2, "data_type": "monetary"},
    }


# Mock API URL and headers
API_URL = "http://mockapi.com"
HEADERS = {"Authorization": "Token mocktoken"}


# Positive test cases
def test_fetch_tags_success():
    mock_response = {"results": [{"name": "tag1", "id": 1}, {"name": "tag2", "id": 2}]}
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        tags = fetch_tags(API_URL, HEADERS)
        assert tags == {"tag1": 1, "tag2": 2}


def test_create_tag_success():
    mock_response = {"id": 1}
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = mock_response

        tag_id = create_tag(API_URL, HEADERS, "new_tag")
        assert tag_id == 1


def test_fetch_or_create_tag_fetch_success():
    mock_response = {"results": [{"name": "tag1", "id": 1}]}
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        tag_id = fetch_or_create_tag(API_URL, HEADERS, "tag1")
        assert tag_id == 1


def test_fetch_or_create_tag_create_success():
    mock_get_response = {"results": []}
    mock_post_response = {"id": 2}
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_get_response

        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = mock_post_response

        tag_id = fetch_or_create_tag(API_URL, HEADERS, "new_tag")
        assert tag_id == 2


def test_fetch_correspondents_success(monkeypatch):
    fake_response = {"results": [{"name": "John Doe", "id": 1}]}

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_response

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())
    result = fetch_correspondents(API_URL, HEADERS)
    assert result == {"John Doe": 1}


def test_create_correspondent_success(monkeypatch):
    fake_response = {"id": 1}

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_response

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: MockResponse())
    result = create_correspondent(API_URL, HEADERS, "John Doe")
    assert result == 1


def test_ensure_custom_field_exists_success(monkeypatch):
    fake_response = {"results": [{"id": 1, "name": "Field", "data_type": "string"}]}

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_response

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())
    result = ensure_custom_field_exists(API_URL, HEADERS, "Field")
    assert result == {"id": 1, "name": "Field", "data_type": "string"}


def test_fetch_ocr_data_success(monkeypatch):
    fake_response = {"content": "Sample OCR Data"}

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_response

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())
    result = fetch_ocr_data(API_URL, HEADERS, 123)
    assert result == "Sample OCR Data"


# Negative test cases
def test_fetch_tags_failure():
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 500

        tags = fetch_tags(API_URL, HEADERS)
        assert tags == {}


def test_create_tag_failure():
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 500
        mock_post.return_value.json.return_value = {}
        mock_post.return_value.raise_for_status.side_effect = (
            requests.exceptions.HTTPError
        )

        tag_id = create_tag(API_URL, HEADERS, "new_tag")
        assert tag_id is None


def test_fetch_or_create_tag_fetch_failure():
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 500
        mock_get.return_value.raise_for_status.side_effect = (
            requests.exceptions.HTTPError
        )

        with pytest.raises(Exception):
            fetch_or_create_tag(API_URL, HEADERS, "tag1")


def test_fetch_or_create_tag_create_failure():
    mock_get_response = {"results": []}
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_get_response

        mock_post.return_value.status_code = 500
        mock_post.return_value.raise_for_status.side_effect = (
            requests.exceptions.HTTPError
        )

        with pytest.raises(Exception):
            fetch_or_create_tag(API_URL, HEADERS, "new_tag")


def test_add_tag_to_document_success():
    mock_response = {"tags": [1, 2, 3]}
    with patch("requests.get") as mock_get, patch("requests.patch") as mock_patch:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"tags": [1, 2]}

        mock_patch.return_value.status_code = 200
        mock_patch.return_value.json.return_value = mock_response

        add_tag_to_document(API_URL, HEADERS, 123, 3)
        mock_patch.assert_called_once()


def test_add_tag_to_document_failure_requests():
    with patch("requests.get") as mock_get, patch("requests.patch") as mock_patch:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"tags": [1, 2]}

        mock_patch.return_value.status_code = 500

        with pytest.raises(Exception, match="Failed to add tag 3 to document 123"):
            add_tag_to_document(API_URL, HEADERS, 123, 3)


def test_fetch_or_create_tag_logging(monkeypatch):
    """Test logging when tag creation fails."""
    mock_get_response = {"results": []}
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_get_response

        mock_post.return_value.status_code = 500
        mock_post.return_value.raise_for_status.side_effect = (
            requests.exceptions.HTTPError
        )

        with pytest.raises(Exception, match="Failed to create tag 'new_tag'."):
            fetch_or_create_tag(API_URL, HEADERS, "new_tag")


def test_add_tag_to_document_logging(monkeypatch):
    """Test logging when adding a tag to a document fails."""
    with patch("requests.get") as mock_get, patch("requests.patch") as mock_patch:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"tags": [1, 2]}

        mock_patch.return_value.status_code = 500
        mock_patch.return_value.raise_for_status.side_effect = (
            requests.exceptions.HTTPError
        )

        with pytest.raises(Exception, match="Failed to add tag 3 to document 123"):
            add_tag_to_document(API_URL, HEADERS, 123, 3)


def test_fetch_correspondents_empty_response(monkeypatch):
    """Test fetch_correspondents with an empty response."""
    fake_response = {"results": []}

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_response

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())
    result = fetch_correspondents(API_URL, HEADERS)
    assert result == {}


def test_create_correspondent_failure(monkeypatch):
    """Test create_correspondent when the API call fails."""

    class MockResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("Failed to create correspondent")

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: MockResponse())
    result = create_correspondent(API_URL, HEADERS, "John Doe")
    assert result is None


def test_ensure_custom_field_exists_creation_failure(monkeypatch):
    """Test ensure_custom_field_exists when field creation fails."""
    fake_get_response = {"results": []}

    class MockGetResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_get_response

    class MockPostResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("Failed to create custom field")

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockGetResponse())
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: MockPostResponse())

    with pytest.raises(Exception, match="Failed to ensure custom field 'Field'."):
        ensure_custom_field_exists(API_URL, HEADERS, "Field")


def test_fetch_ocr_data_failure_monkeypatch(monkeypatch):
    """Test fetch_ocr_data when the API call fails."""

    class MockResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("Failed to fetch OCR data")

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    with pytest.raises(Exception, match="Failed to fetch OCR data for document ID 123"):
        fetch_ocr_data(API_URL, HEADERS, 123)


def test_dummy_import():
    assert fetch_tags is not None


def test_fetch_or_create_tag_failure():
    """Test fetch_or_create_tag when tag creation fails."""
    with patch("utils.api_helpers.fetch_tags", return_value={}), patch(
        "utils.api_helpers.create_tag", return_value=None
    ):
        with pytest.raises(Exception, match="Failed to create tag 'new_tag'."):
            fetch_or_create_tag(API_URL, HEADERS, "new_tag")


def test_add_tag_to_document_failure_apihelpers():
    """Test add_tag_to_document when API call fails."""
    with patch(
        "utils.api_helpers.fetch_document_details", return_value={"tags": []}
    ), patch("utils.api_helpers.requests.patch", side_effect=Exception("API error")):
        with pytest.raises(Exception, match="Failed to add tag 123 to document 456."):
            add_tag_to_document(API_URL, HEADERS, 456, 123)


def test_ensure_custom_field_exists_failure():
    """Test ensure_custom_field_exists when API call fails."""
    with patch("utils.api_helpers.requests.get", side_effect=Exception("API error")):
        with pytest.raises(
            Exception, match="Failed to ensure custom field 'mock_field'."
        ):
            ensure_custom_field_exists(API_URL, HEADERS, "mock_field")


def test_fetch_ocr_data_failure_patch():
    """Test fetch_ocr_data when API call fails."""
    with patch("utils.api_helpers.requests.get", side_effect=Exception("API error")):
        with pytest.raises(
            Exception, match="Failed to fetch OCR data for document ID 789."
        ):
            fetch_ocr_data(API_URL, HEADERS, 789)
