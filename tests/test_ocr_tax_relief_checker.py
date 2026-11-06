import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Explicitly set the `PYTHONPATH` to include the `src` directory
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
os.environ["PYTHONPATH"] = src_path
if src_path not in sys.path:
    sys.path.insert(0, src_path)

os.environ.setdefault("OPENAI_API_KEY", "test")

import httpx  # noqa: E402
import openai  # noqa: E402

import ocr_tax_relief_checker as checker  # noqa: E402
from ocr_tax_relief_checker import analyze_document_with_openai  # noqa: E402


def mock_openai_response(valid=True):
    if valid:
        return MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {
                                "detected_services": [
                                    {
                                        "description": "Broadband",
                                        "category": "Utilities",
                                        "allowable": True,
                                        "disallow_reason": "",
                                        "amount": 50.0,
                                    }
                                ],
                                "total_amount_claimable": 50.0,
                                "covered_under": "PAYE",
                                "confidence_score": 0.95,
                                "analysis": "Broadband is allowable under utilities.",
                            }
                        )
                    )
                )
            ]
        )
    else:
        return MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {"invalid_field": "This is an invalid response"}
                        )
                    )
                )
            ]
        )


@patch("ocr_tax_relief_checker.client.chat.completions.create")
def test_analyze_document_with_openai_valid(mock_create):
    mock_create.return_value = mock_openai_response(valid=True)

    ocr_data = "Sample OCR data"
    document_id = 123
    result = analyze_document_with_openai(ocr_data, document_id)

    assert result is not None
    assert "detected_services" in json.loads(result)


@patch("requests.post")
@patch(
    "ocr_tax_relief_checker.fetch_or_create_tag",
    side_effect=Exception("Failed to create tag"),
)
@patch("ocr_tax_relief_checker.client.chat.completions.create")
def test_analyze_document_with_openai_invalid(
    mock_create, mock_fetch_or_create_tag, mock_post
):
    """A tagging failure is logged, and the failure note is still posted."""
    mock_create.return_value = mock_openai_response(valid=False)

    result = analyze_document_with_openai("Sample OCR data", 123)

    assert result is None
    mock_fetch_or_create_tag.assert_called_once()
    mock_post.assert_called_once()
    assert "Validation error" in mock_post.call_args.kwargs["json"]["note"]


@patch("ocr_tax_relief_checker.record_failure")
@patch("ocr_tax_relief_checker.add_tag_to_document")
@patch("ocr_tax_relief_checker.fetch_or_create_tag", return_value=1)
@patch("ocr_tax_relief_checker.client.chat.completions.create")
def test_analyze_document_with_openai_failure_records_note(
    mock_create, mock_fetch_or_create_tag, mock_add_tag, mock_record_failure
):
    mock_create.return_value = mock_openai_response(valid=False)

    ocr_data = "Sample OCR data"
    document_id = 123

    result = analyze_document_with_openai(ocr_data, document_id)

    assert result is None
    mock_record_failure.assert_called_once()


def _api_error(cls, status, headers=None):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status, request=request, headers=headers or {})
    return cls("error", response=response, body=None)


@patch("ocr_tax_relief_checker.record_failure")
@patch("ocr_tax_relief_checker.client.chat.completions.create")
def test_analyze_api_error_records_failure_once(mock_create, mock_record_failure):
    """An OpenAI error such as a retired model is recorded once, not crashed on."""
    mock_create.side_effect = _api_error(openai.NotFoundError, 404)

    result = analyze_document_with_openai("Sample OCR data", 123)

    assert result is None
    mock_create.assert_called_once()
    mock_record_failure.assert_called_once()
    assert "OpenAI API error" in mock_record_failure.call_args.args[1]


@patch("ocr_tax_relief_checker.time.sleep")
@patch("ocr_tax_relief_checker.record_failure")
@patch("ocr_tax_relief_checker.client.chat.completions.create")
def test_analyze_retries_rate_limit_using_retry_after(
    mock_create, mock_record_failure, mock_sleep
):
    mock_create.side_effect = [
        _api_error(openai.RateLimitError, 429, {"retry-after": "3"}),
        mock_openai_response(valid=True),
    ]

    result = analyze_document_with_openai("Sample OCR data", 123)

    assert result is not None
    mock_sleep.assert_called_once_with(3.0)
    mock_record_failure.assert_not_called()


@patch("ocr_tax_relief_checker.record_failure")
@patch("ocr_tax_relief_checker.client.chat.completions.create")
def test_analyze_non_json_response_records_failure(mock_create, mock_record_failure):
    mock_create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="not json"))]
    )

    assert analyze_document_with_openai("Sample OCR data", 123) is None
    mock_record_failure.assert_called_once()
    assert "JSON decode error" in mock_record_failure.call_args.args[1]


def test_main_does_not_record_analysis_failure_twice(monkeypatch):
    monkeypatch.setattr(checker, "fetch_document_ocr", lambda doc_id: "text")
    monkeypatch.setattr(checker, "analyze_document_with_openai", lambda *a: None)
    record_failure = MagicMock()
    monkeypatch.setattr(checker, "record_failure", record_failure)
    monkeypatch.setattr(sys, "argv", ["ocr_tax_relief_checker.py", "123"])

    with pytest.raises(SystemExit) as exc:
        checker.main()

    assert exc.value.code == 1
    record_failure.assert_not_called()


def test_main_creates_custom_fields_before_looking_up_ids(monkeypatch):
    calls = []
    monkeypatch.setattr(checker, "fetch_document_ocr", lambda doc_id: "text")
    monkeypatch.setattr(
        checker, "analyze_document_with_openai", lambda *a: json.dumps({})
    )
    monkeypatch.setattr(
        checker, "ensure_custom_fields", lambda *a: calls.append("ensure")
    )
    monkeypatch.setattr(
        checker, "populate_field_mapping_with_ids", lambda *a: calls.append("ids")
    )
    monkeypatch.setattr(checker, "update_document_with_json", lambda *a: None)
    monkeypatch.setattr(sys, "argv", ["ocr_tax_relief_checker.py", "123"])

    checker.main()

    assert calls == ["ensure", "ids"]


def test_update_document_with_json_skips_fields_without_id(monkeypatch):
    monkeypatch.setattr(
        checker,
        "field_mapping",
        {
            "covered_under": {"name": "covered_under", "id": 7},
            "confidence_score": {"name": "confidence_score"},
        },
    )
    update = MagicMock()
    monkeypatch.setattr(checker, "update_document", update)

    checker.update_document_with_json(
        "http://api", {}, 1, {"covered_under": "PAYE", "confidence_score": 0.9}
    )

    payload = update.call_args.args[3]
    assert payload == {"custom_fields": [{"field": 7, "value": "PAYE"}]}
