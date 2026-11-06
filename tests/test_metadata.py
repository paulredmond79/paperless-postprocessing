import pytest
from conftest import FakeAI, FakePaperless

from postprocessing.ai import AIError
from postprocessing.metadata import (
    MAX_OCR_CHARS,
    MAX_TEXT_LENGTH,
    SYSTEM_MESSAGE,
    apply_metadata,
    build_prompt,
    clean_fields,
    field_definitions,
    parse_amount,
    reply_schema,
    to_snake_case,
    truncate_text,
)

FIELDS = [
    {"id": 1, "name": "Company Name", "data_type": "string"},
    {"id": 2, "name": "Total Amount", "data_type": "monetary"},
    {"id": 3, "name": "Due Date", "data_type": "date"},
]


def test_to_snake_case():
    assert to_snake_case(" Example---Test! ") == "example_test"
    assert to_snake_case("Due Date") == "due_date"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("€1,291.81", 1291.81),
        ("1.291,81", 1291.81),
        ("1234,50", 1234.5),
        ("1 234,50", 1234.5),
        ("1,291", 1291.0),
        ("1.291.000", 1291000.0),
        ("EUR 57,747.20", 57747.2),
    ],
)
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


def test_clean_fields_by_type():
    definitions = {
        "total": {"data_type": "monetary"},
        "score": {"data_type": "float"},
        "count": {"data_type": "integer"},
        "paid": {"data_type": "boolean"},
        "issued": {"data_type": "date"},
        "notes": {"data_type": "string"},
        "status": {"data_type": "select"},
    }
    fields = {
        "total": "€1,291.81",
        "score": "0.98",
        "count": "3",
        "paid": "No",
        "issued": "29 Oct 2026",
        "notes": "x" * 300,
        "status": "Unpaid",
        "unknown": "value",
    }

    cleaned = clean_fields(fields, definitions)

    assert cleaned == {
        "total": "1291.81",
        "score": 0.98,
        "count": 3,
        "paid": False,
        "issued": "2026-10-29",
        "notes": "x" * (MAX_TEXT_LENGTH - 1) + "…",
    }


def test_clean_fields_skips_unparseable_values_without_logging_them(caplog):
    definitions = {"due": {"data_type": "date"}, "total": {"data_type": "monetary"}}

    cleaned = clean_fields({"due": "Immediately", "total": "overleaf"}, definitions)

    assert cleaned == {}
    assert "Immediately" not in caplog.text
    assert "overleaf" not in caplog.text


def test_truncate_text_leaves_short_text():
    assert truncate_text("short") == "short"


def test_field_definitions_keeps_oldest_of_duplicate_names(caplog):
    # Paperless listed the newer snake_case copy first on the real instance
    definitions = field_definitions(
        [
            {"id": 19, "name": "confidence_score", "data_type": "float"},
            {"id": 13, "name": "Confidence Score", "data_type": "float"},
        ]
    )

    assert definitions == {"confidence_score": {"id": 13, "data_type": "float"}}
    assert "19" in caplog.text


def test_clean_fields_skips_null_values():
    definitions = {"due": {"data_type": "date"}, "notes": {"data_type": "string"}}

    assert clean_fields({"due": None, "notes": None}, definitions) == {}


def test_prompt_holds_only_capped_ocr_text():
    prompt = build_prompt("x" * (MAX_OCR_CHARS + 500))

    assert "x" * MAX_OCR_CHARS in prompt
    assert "x" * (MAX_OCR_CHARS + 1) not in prompt


def test_reply_schema_has_a_nullable_property_per_fillable_field():
    definitions = field_definitions(
        FIELDS + [{"id": 4, "name": "Payment Status", "data_type": "select"}]
    )

    schema = reply_schema(definitions)["schema"]
    fields = schema["properties"]["fields"]

    assert schema["required"] == ["title", "fields"]
    assert fields["required"] == ["company_name", "total_amount", "due_date"]
    assert fields["properties"]["total_amount"]["type"] == ["number", "null"]
    assert fields["properties"]["due_date"]["type"] == ["string", "null"]
    assert "payment_status" not in fields["properties"]  # select needs IDs
    assert fields["additionalProperties"] is False


def test_apply_metadata_sends_the_schema(document):
    paperless = FakePaperless(documents=[document], fields=FIELDS)
    ai = FakeAI({"title": "ESB bill", "fields": {"due_date": None}})

    apply_metadata(paperless, ai, document)

    assert ai.schemas == [reply_schema(field_definitions(FIELDS))]
    _, changes = paperless.updates[-1]
    assert "custom_fields" not in changes  # a null value isn't written


def test_apply_metadata_sets_title_and_merges_fields(document):
    document["custom_fields"] = [
        {"field": 3, "value": "2026-01-01"},
        {"field": 9, "value": "kept"},
    ]
    paperless = FakePaperless(documents=[document], fields=FIELDS)
    ai = FakeAI(
        {
            "title": "ESB bill",
            "fields": {"company_name": "ESB", "total_amount": "1,291.81"},
        }
    )

    result = apply_metadata(paperless, ai, document)

    assert result.title_set and result.fields_set == 2
    doc_id, changes = paperless.updates[-1]
    assert changes["title"] == "ESB bill"
    assert {cf["field"]: cf["value"] for cf in changes["custom_fields"]} == {
        1: "ESB",
        2: "1291.81",
        3: "2026-01-01",
        9: "kept",
    }


def test_apply_metadata_stays_within_paperless_limits(document):
    paperless = FakePaperless(documents=[document], fields=FIELDS)
    ai = FakeAI({"title": "T" * 200, "fields": {"company_name": "n" * 237}})

    apply_metadata(paperless, ai, document)

    _, changes = paperless.updates[-1]
    assert len(changes["title"]) == MAX_TEXT_LENGTH
    assert len(changes["custom_fields"][0]["value"]) == MAX_TEXT_LENGTH


def test_apply_metadata_keeps_title_when_none_returned(document):
    paperless = FakePaperless(documents=[document], fields=FIELDS)

    result = apply_metadata(paperless, FakeAI({"title": "", "fields": {}}), document)

    assert not result.title_set
    assert paperless.updates == []


def test_apply_metadata_sets_title_without_custom_fields(document):
    paperless = FakePaperless(documents=[document], fields=[])

    apply_metadata(paperless, FakeAI({"title": "ESB bill", "fields": {}}), document)

    assert paperless.updates == [(296, {"title": "ESB bill"})]


def test_apply_metadata_rejects_bad_fields_shape(document):
    paperless = FakePaperless(documents=[document], fields=FIELDS)

    with pytest.raises(AIError):
        apply_metadata(paperless, FakeAI({"title": "T", "fields": ["x"]}), document)


def test_system_message_lists_the_household_properties():
    for name in ("Sycamore Close", "Parkwest", "Caiseal Cam"):
        assert name in SYSTEM_MESSAGE.replace(" \\n", " ").replace("\n", " ")


def test_clean_fields_keeps_native_json_numbers():
    definitions = {
        "score": {"data_type": "float"},
        "count": {"data_type": "integer"},
        "total": {"data_type": "monetary"},
        "big": {"data_type": "monetary"},
    }
    fields = {"score": 0.00001, "count": 2**31 - 1, "total": 1291.8}
    fields["big"] = 9999999999.99

    cleaned = clean_fields(fields, definitions)

    assert cleaned["score"] == 0.00001
    assert cleaned["count"] == 2147483647
    assert cleaned["total"] == "1291.80"
    assert cleaned["big"] == "9999999999.99"


@pytest.mark.parametrize(
    "key, value",
    [
        ("total", 1e10),
        ("total", -1e20),
        ("count", 2**31),
        ("count", -(2**31) - 1),
        ("count", 12345678901234567891),
    ],
)
def test_clean_fields_skips_values_beyond_paperless_limits(key, value):
    definitions = {
        "total": {"data_type": "monetary"},
        "count": {"data_type": "integer"},
    }

    assert clean_fields({key: value}, definitions) == {}


def test_clean_fields_accepts_lowest_integer():
    definitions = {"count": {"data_type": "integer"}}

    assert clean_fields({"count": -(2**31)}, definitions) == {"count": -(2**31)}


def test_apply_metadata_merges_with_fields_changed_during_the_call(document):
    paperless = FakePaperless(documents=[document], fields=FIELDS)
    # Someone sets a field after the pipeline fetched the document
    paperless.documents[296]["custom_fields"] = [{"field": 9, "value": "new"}]
    ai = FakeAI({"title": "ESB bill", "fields": {"company_name": "ESB"}})

    apply_metadata(paperless, ai, document)

    _, changes = paperless.updates[-1]
    assert {cf["field"]: cf["value"] for cf in changes["custom_fields"]} == {
        1: "ESB",
        9: "new",
    }


@pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
def test_clean_fields_rejects_non_numbers_for_number_fields(value):
    definitions = {
        "total": {"data_type": "monetary"},
        "count": {"data_type": "integer"},
    }

    assert clean_fields({"total": value, "count": value}, definitions) == {}
