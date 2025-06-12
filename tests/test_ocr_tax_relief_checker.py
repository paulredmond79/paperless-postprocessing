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


@patch(
    "utils.api_helpers.fetch_or_create_tag",
    side_effect=Exception("Failed to create tag"),
)
@patch("ocr_tax_relief_checker.client.chat.completions.create")
def test_analyze_document_with_openai_invalid(mock_create, mock_fetch_or_create_tag):
    mock_create.return_value = mock_openai_response(valid=False)

    ocr_data = "Sample OCR data"
    document_id = 123

    with pytest.raises(Exception, match="Failed to create tag"):
        analyze_document_with_openai(ocr_data, document_id)
