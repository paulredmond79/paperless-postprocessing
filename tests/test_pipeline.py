from conftest import SECRET, FakeAI, FakePaperless

from postprocessing.ai import AIError
from postprocessing.correspondent import PROCESSED_TAG
from postprocessing.paperless import PaperlessError
from postprocessing.pipeline import process_document

FIELDS = [{"id": 1, "name": "Company Name", "data_type": "string"}]


def test_runs_correspondent_then_metadata(document):
    paperless = FakePaperless(documents=[document], fields=FIELDS)
    ai = FakeAI(
        {"status": "suggest_new", "correspondent": "ESB Networks"},
        {"title": "ESB bill", "fields": {"company_name": "ESB"}},
    )

    assert process_document(paperless, ai, 296) is True

    saved = paperless.documents[296]
    assert paperless.correspondents[saved["correspondent"]]["name"] == "ESB Networks"
    assert saved["title"] == "ESB bill"
    assert PROCESSED_TAG in {paperless.tags[t]["name"] for t in saved["tags"]}


def test_failed_step_does_not_stop_the_next(document):
    paperless = FakePaperless(documents=[document], fields=FIELDS)
    ai = FakeAI(AIError("model_not_found"), {"title": "ESB bill", "fields": {}})

    assert process_document(paperless, ai, 296) is False
    assert paperless.documents[296]["title"] == "ESB bill"


def test_only_runs_requested_steps(document):
    paperless = FakePaperless(documents=[document], fields=FIELDS)
    ai = FakeAI({"title": "ESB bill", "fields": {}})

    assert process_document(paperless, ai, 296, ["metadata"]) is True
    assert paperless.documents[296]["correspondent"] is None


def test_document_without_ocr_is_skipped(document):
    document["content"] = "  "
    paperless = FakePaperless(documents=[document])

    assert process_document(paperless, FakeAI(), 296) is True
    assert paperless.updates == []


def test_fetch_failure_returns_false():
    class Broken(FakePaperless):
        def get_document(self, doc_id):
            raise PaperlessError("HTTP 404")

    assert process_document(Broken(), FakeAI(), 1) is False


def test_document_text_is_never_logged(document, caplog):
    caplog.set_level("DEBUG")
    paperless = FakePaperless(documents=[document], fields=FIELDS)
    ai = FakeAI(
        {"status": "suggest_new", "correspondent": "ESB Networks"},
        {"title": "ESB bill", "fields": {"company_name": SECRET}},
    )

    process_document(paperless, ai, 296)

    assert SECRET in ai.prompts[0]  # sent to OpenAI
    assert SECRET not in caplog.text  # but never logged
