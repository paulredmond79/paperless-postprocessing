"""Tests for the command-line scripts in src/, using in-memory fakes."""

import pytest
from conftest import FakeAI, FakePaperless

import cleanup_correspondents
import merge_duplicates
import post
import postprocess_all
from postprocessing import cli
from postprocessing.config import ConfigError


def use_fakes(monkeypatch, module, paperless, ai=None):
    monkeypatch.setattr(module, "build_clients", lambda **kwargs: (paperless, ai))


# post.py


def test_post_runs_both_steps(monkeypatch, document):
    paperless = FakePaperless(documents=[document])
    ai = FakeAI(
        {"status": "suggest_new", "correspondent": "ESB Networks"},
        {"title": "ESB bill", "fields": {}},
    )
    use_fakes(monkeypatch, post, paperless, ai)

    assert post.main(["296"]) == cli.EXIT_OK
    assert paperless.documents[296]["title"] == "ESB bill"
    assert paperless.documents[296]["correspondent"] is not None


def test_post_only_flag(monkeypatch, document):
    paperless = FakePaperless(documents=[document])
    use_fakes(monkeypatch, post, paperless, FakeAI({"title": "ESB bill", "fields": {}}))

    assert post.main(["296", "--only", "metadata"]) == cli.EXIT_OK
    assert paperless.documents[296]["correspondent"] is None


def test_post_reads_document_id_from_paperless_env(monkeypatch):
    monkeypatch.setenv("DOCUMENT_ID", "296")

    assert post.parse_args([]).document_id == "296"


@pytest.mark.parametrize("argv", [[], ["abc"]])
def test_post_rejects_missing_or_bad_id(monkeypatch, argv):
    monkeypatch.delenv("DOCUMENT_ID", raising=False)

    with pytest.raises(SystemExit):
        post.parse_args(argv)


def test_post_returns_failure_when_a_step_fails(monkeypatch, document):
    paperless = FakePaperless(documents=[document])
    ai = FakeAI({"status": "nonsense"}, {"title": "ESB bill", "fields": {}})
    use_fakes(monkeypatch, post, paperless, ai)

    assert post.main(["296"]) == cli.EXIT_FAILED


def test_run_turns_missing_settings_into_exit_2(caplog):
    def main(argv):
        raise ConfigError("Missing setting(s): PAPERLESS_API_TOKEN.")

    assert cli.run(main, []) == cli.EXIT_CONFIG
    assert "PAPERLESS_API_TOKEN" in caplog.text


# postprocess_all.py


def make_docs():
    return [
        {"id": 1, "content": "a", "tags": [5], "correspondent": None},
        {"id": 2, "content": "b", "tags": [], "correspondent": None},
        {"id": 3, "content": "c", "tags": [], "correspondent": None},
    ]


def test_batch_skips_processed_documents(monkeypatch):
    paperless = FakePaperless(
        documents=make_docs(), tags=[{"id": 5, "name": "gpt-correspondent"}]
    )
    ai = FakeAI(
        {"status": "suggest_new", "correspondent": "B Ltd"},
        {"status": "suggest_new", "correspondent": "C Ltd"},
    )
    use_fakes(monkeypatch, postprocess_all, paperless, ai)

    assert postprocess_all.main([]) == cli.EXIT_OK
    assert {doc_id for doc_id, _ in paperless.updates} == {2, 3}


def test_batch_continues_after_failure_and_reports_it(monkeypatch):
    paperless = FakePaperless(documents=make_docs())
    ai = FakeAI(
        {"status": "nonsense"},
        {"status": "suggest_new", "correspondent": "B Ltd"},
        {"status": "suggest_new", "correspondent": "C Ltd"},
    )
    use_fakes(monkeypatch, postprocess_all, paperless, ai)

    assert postprocess_all.main([]) == cli.EXIT_FAILED
    assert paperless.documents[3]["correspondent"] is not None


def test_batch_limit(monkeypatch):
    paperless = FakePaperless(documents=make_docs())
    ai = FakeAI({"status": "suggest_new", "correspondent": "A Ltd"})
    use_fakes(monkeypatch, postprocess_all, paperless, ai)

    assert postprocess_all.main(["--limit", "1"]) == cli.EXIT_OK
    assert ai.replies == []


# cleanup_correspondents.py


def json_named_paperless():
    return FakePaperless(
        correspondents=[
            {"id": 1, "name": '{"correspondent": "ESB Networks"}'},
            {"id": 2, "name": "AIB"},
        ]
    )


def test_cleanup_reports_by_default(monkeypatch):
    paperless = json_named_paperless()
    use_fakes(monkeypatch, cleanup_correspondents, paperless)

    assert cleanup_correspondents.main([]) == cli.EXIT_OK
    assert paperless.correspondents[1]["name"].startswith("{")


def test_cleanup_apply_renames(monkeypatch):
    paperless = json_named_paperless()
    use_fakes(monkeypatch, cleanup_correspondents, paperless)

    cleanup_correspondents.main(["--apply"])

    assert paperless.correspondents[1]["name"] == "ESB Networks"
    assert paperless.correspondents[2]["name"] == "AIB"


# merge_duplicates.py


def duplicate_paperless():
    return FakePaperless(
        correspondents=[
            {"id": 1, "name": "ESB Networks"},
            {"id": 2, "name": "esb  networks"},
            {"id": 3, "name": "AIB"},
        ],
        documents=[{"id": 10, "correspondent": 2, "tags": []}],
    )


def test_merge_reports_by_default(monkeypatch):
    paperless = duplicate_paperless()
    use_fakes(monkeypatch, merge_duplicates, paperless)

    assert merge_duplicates.main([]) == cli.EXIT_OK
    assert paperless.deleted_correspondents == []
    assert paperless.documents[10]["correspondent"] == 2


def test_merge_apply_moves_documents_and_keeps_names(monkeypatch):
    paperless = duplicate_paperless()
    use_fakes(monkeypatch, merge_duplicates, paperless)

    merge_duplicates.main(["--apply"])

    assert paperless.documents[10]["correspondent"] == 1
    assert paperless.deleted_correspondents == [2]
    assert paperless.correspondents[1]["name"] == "ESB Networks"
    assert paperless.correspondents[3]["name"] == "AIB"
