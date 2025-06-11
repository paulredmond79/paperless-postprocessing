import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
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
