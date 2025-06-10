import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import postprocess_all


def test_skip_documents_with_tag_dicts(monkeypatch):
    docs = [
        {"id": 1, "tags": [{"id": 5}]},
        {"id": 2, "tags": [4, {"id": 5}]},
        {"id": 3, "tags": [4]},
    ]

    monkeypatch.setattr(postprocess_all, "fetch_all_documents", lambda: docs)
    monkeypatch.setattr(
        postprocess_all, "fetch_tags", lambda: {"gpt-correspondent": {"id": 5}}
    )

    processed = []

    def fake_process_document(doc_id):
        processed.append(doc_id)

    monkeypatch.setattr(postprocess_all, "process_document", fake_process_document)

    postprocess_all.main()

    assert processed == [3]
