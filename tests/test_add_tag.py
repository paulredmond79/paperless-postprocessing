import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import postprocess  # noqa: E402


def test_add_tag_preserves_existing(monkeypatch):
    postprocess.paperless_url = "http://api"
    postprocess.headers = {}

    def fake_fetch_document_details(doc_id):
        assert doc_id == 1
        return {"tags": [{"id": 2}, 3]}

    class Resp:
        def raise_for_status(self):
            pass

    captured = {}

    def fake_patch(url, headers=None, json=None):
        captured["url"] = url
        captured["json"] = json
        return Resp()

    monkeypatch.setattr(
        postprocess, "fetch_document_details", fake_fetch_document_details
    )
    monkeypatch.setattr(postprocess.requests, "patch", fake_patch)

    postprocess.add_tag_to_document(1, 5)
    assert set(captured["json"]["tags"]) == {2, 3, 5}
    assert captured["url"] == "http://api/api/documents/1/"
