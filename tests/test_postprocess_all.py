import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

import postprocess_all  # noqa: E402


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


def test_batch_continues_after_failures(monkeypatch):
    docs = [{"id": 1, "tags": []}, {"id": 2, "tags": []}, {"id": 3, "tags": []}]
    monkeypatch.setattr(postprocess_all, "fetch_all_documents", lambda: docs)
    monkeypatch.setattr(
        postprocess_all, "fetch_tags", lambda: {"gpt-correspondent": {"id": 5}}
    )

    processed = []

    def fake_process_document(doc_id):
        processed.append(doc_id)
        if doc_id == 1:
            sys.exit(1)
        if doc_id == 2:
            raise RuntimeError("boom")

    monkeypatch.setattr(postprocess_all, "process_document", fake_process_document)

    with pytest.raises(SystemExit) as exc:
        postprocess_all.main()

    assert processed == [1, 2, 3]
    assert exc.value.code == 1


def test_batch_treats_exit_zero_as_success(monkeypatch):
    monkeypatch.setattr(
        postprocess_all, "fetch_all_documents", lambda: [{"id": 1, "tags": []}]
    )
    monkeypatch.setattr(
        postprocess_all, "fetch_tags", lambda: {"gpt-correspondent": {"id": 5}}
    )

    def no_ocr(doc_id):
        sys.exit(0)

    monkeypatch.setattr(postprocess_all, "process_document", no_ocr)

    postprocess_all.main()
