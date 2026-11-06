import pytest
from conftest import FakeAI, FakePaperless

from postprocessing.ai import AIError
from postprocessing.correspondent import (
    MAX_OCR_CHARS,
    PROCESSED_TAG,
    REPLY_SCHEMA,
    UNDETERMINED_TAG,
    build_prompt,
    choose_correspondent,
    detect_correspondent,
)


def paperless_with(document, correspondents=()):
    return FakePaperless(
        documents=[document],
        tags=[{"id": 1, "name": "Inbox"}],
        correspondents=list(correspondents),
    )


def tag_names(paperless, doc_id):
    ids = paperless.documents[doc_id]["tags"]
    return {paperless.tags[i]["name"] for i in ids}


def test_match_assigns_existing_correspondent_and_tags(document):
    paperless = paperless_with(document, [{"id": 4, "name": "ESB Networks"}])
    ai = FakeAI({"status": "match", "correspondent": "esb networks"})

    result = detect_correspondent(paperless, ai, document)

    assert result.status == "assigned"
    assert paperless.documents[296]["correspondent"] == 4
    assert tag_names(paperless, 296) == {"Inbox", PROCESSED_TAG}
    assert len(paperless.correspondents) == 1


def test_suggest_new_creates_correspondent(document):
    paperless = paperless_with(document)
    ai = FakeAI({"status": "suggest_new", "correspondent": "ESB Networks"})

    result = detect_correspondent(paperless, ai, document)

    assert result.name == "ESB Networks"
    new_id = paperless.documents[296]["correspondent"]
    assert paperless.correspondents[new_id]["name"] == "ESB Networks"


def test_unchanged_correspondent_is_still_tagged(document):
    document["correspondent"] = 4
    paperless = paperless_with(document, [{"id": 4, "name": "ESB Networks"}])
    ai = FakeAI({"status": "match", "correspondent": "ESB Networks"})

    result = detect_correspondent(paperless, ai, document)

    assert result.status == "unchanged"
    assert all("correspondent" not in changes for _, changes in paperless.updates)
    assert PROCESSED_TAG in tag_names(paperless, 296)


@pytest.mark.parametrize(
    "reply",
    [
        {"status": "no_match", "reason": "unclear"},
        {
            "status": "suggest_new",
            "correspondent": "The OCR text does not provide a clear correspondent name.",
        },
    ],
)
def test_undetermined_tags_document_and_creates_nothing(document, reply):
    paperless = paperless_with(document)

    result = detect_correspondent(paperless, FakeAI(reply), document)

    assert result.status == "undetermined"
    assert paperless.correspondents == {}
    assert paperless.documents[296]["correspondent"] is None
    assert tag_names(paperless, 296) == {"Inbox", UNDETERMINED_TAG}


@pytest.mark.parametrize(
    "reply",
    [
        {"status": "maybe"},
        {"status": "match"},
        {"status": "match", "correspondent": " "},
    ],
)
def test_malformed_reply_raises(reply):
    with pytest.raises(AIError):
        choose_correspondent(FakeAI(reply), "text", [])


def test_prompt_lists_all_correspondents_and_caps_ocr():
    names = [f"Company {i}" for i in range(60)]
    prompt = build_prompt("x" * (MAX_OCR_CHARS + 500), names)

    assert "Company 59" in prompt  # the old limit of 50 dropped these
    assert "x" * MAX_OCR_CHARS in prompt
    assert "x" * (MAX_OCR_CHARS + 1) not in prompt


def test_prompt_lists_one_name_per_line_sorted():
    prompt = build_prompt("text", ["zeta", "Acme, Ltd", "beta"])

    assert "- Acme, Ltd\n- beta\n- zeta" in prompt


def test_prompt_with_no_correspondents():
    assert "(none yet)" in build_prompt("text", [])


def test_choose_correspondent_sends_the_reply_schema():
    ai = FakeAI({"status": "match", "correspondent": "ESB"})

    choose_correspondent(ai, "text", ["ESB"])

    assert ai.schemas == [REPLY_SCHEMA]
