"""Generating a document title and filling custom fields with OpenAI."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime

from postprocessing.ai import AIError

# Paperless rejects titles and string custom field values longer than this,
# and one over-long value makes it reject the whole update.
MAX_TEXT_LENGTH = 128

# Long documents are cut to this length before they're sent to OpenAI
MAX_OCR_CHARS = 20000

# The instructions are fixed and come first; only the user message varies
SYSTEM_MESSAGE = """\
You write titles and extract metadata for documents in a personal document \
archive (Paperless-ngx) for a household in Ireland. Amounts are usually in \
euro, and dates are written day first (03/02/2026 is 3 February 2026).

Title:
- Say who it's from, what kind of document it is, and the period or date it \
covers, for example "Electric Ireland electricity bill - March 2026".
- Several people live in the household, so when a document is about one \
person, name them as printed on the document, so it's clear whose it is. \
That covers medical reports, prescriptions, appointment letters, school \
reports, payslips, P60s, tax statements, and insurance or bank documents in \
one person's name. For example: "Beacon Hospital MRI report for Mary Murphy \
- 12 Jan 2026" or "St Mary's NS school report for Jack Murphy - June 2026".
- Leave the person's name out of documents for the whole household, such as \
utility bills, and never name the sender's staff, such as the doctor who \
signed.
- The household owns these properties: Sycamore Close, Parkwest and Caiseal \
Cam. Parkwest is the house on The Crescent in Parkwest Pointe, so a document \
that says "The Crescent" or "Parkwest Pointe" is about Parkwest. When a \
document is about one of them, include its name spelled exactly as in that \
list, whatever the document calls it. That covers mortgage \
statements, mortgage interest certificates, electricity, gas, water and \
broadband bills, property tax, home insurance, rent and repairs. For \
example: "Electric Ireland electricity bill for Caiseal Cam - March 2026". \
If the property isn't one of these, use its street or estate name, without \
the house number, town or Eircode.
- Letters for every property are posted to the household's home address, \
so the address a letter is sent to doesn't say which property it is about. \
Only name a property when the document states it as the property concerned, \
for example a supply address, property address, security or premises. If it \
doesn't, leave the property out of the title.
- Keep it under 100 characters and write it in English.
- Never include personal identifiers such as PPS numbers, account or card \
numbers, or full addresses. A person's name and a property's short name \
are fine.

Fields:
- Fill a field only when the document states its value. Otherwise use null. \
Don't guess, infer or calculate values.
- Use each field only for what its name means. For example, a due date is \
a payment deadline. It isn't the date the document was issued, and it is \
null if the document says to pay "immediately" or "on receipt".
- Amounts are plain numbers, such as 1291.81, with no currency symbol.
- Dates are YYYY-MM-DD.
- Text values are short: a name, a reference number or a few words.

The OCR text may contain recognition errors; for example, € often appears \
as another character."""

# JSON schema type for each Paperless custom field type we can fill
SCHEMA_TYPES = {
    "string": {"type": ["string", "null"]},
    "url": {"type": ["string", "null"]},
    "date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
    "monetary": {"type": ["number", "null"]},
    "float": {"type": ["number", "null"]},
    "integer": {"type": ["integer", "null"]},
    "boolean": {"type": ["boolean", "null"]},
}

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d %b %y",
    "%b %d, %Y",
    "%B %d, %Y",
]


@dataclass
class MetadataResult:
    """What the metadata step did to a document."""

    title_set: bool
    fields_set: int


def to_snake_case(text):
    """Converts text to snake_case, for example 'Due Date' to 'due_date'."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def field_definitions(custom_fields):
    """
    Maps each custom field's snake_case name to its ID and data type.

    If two fields share a snake_case name (for example "Due Date" and
    "due_date"), the oldest one (lowest ID) wins and a warning names the
    other. Paperless's list order is not reliable for this.
    """
    definitions = {}
    for field in sorted(custom_fields, key=lambda f: f["id"]):
        key = to_snake_case(field["name"])
        if key in definitions:
            logging.warning(
                f"Custom fields {definitions[key]['id']} and {field['id']} both "
                f"map to '{key}'. Using field {definitions[key]['id']}."
            )
            continue
        definitions[key] = {"id": field["id"], "data_type": field["data_type"]}
    return definitions


def truncate_text(value, limit=MAX_TEXT_LENGTH):
    """Shortens text to Paperless's length limit, ending it with an ellipsis."""
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def parse_date(value):
    """Converts a date in one of DATE_FORMATS to YYYY-MM-DD."""
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("unsupported date format")


def parse_amount(value):
    """
    Converts an amount such as "€1,291.81", "1.291,81" or "1234,50" to a
    float. When both separators appear, the last one is the decimal point.
    A lone comma followed by exactly three digits is a thousands separator.
    """
    number = re.sub(r"[^\d,.\-]", "", value)
    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    elif "," in number:
        whole, _, fraction = number.rpartition(",")
        if number.count(",") == 1 and len(fraction) != 3:
            number = f"{whole}.{fraction}"
        else:
            number = number.replace(",", "")
    elif number.count(".") > 1:
        number = number.replace(".", "")
    return float(number)


def to_number(value):
    """
    Returns a reply value as a number.

    JSON numbers from the strict schema are used as they are; only text
    goes through ``parse_amount``. Raises ValueError for anything else.
    """
    if isinstance(value, bool):
        raise ValueError("a yes/no value isn't a number")
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("not a finite number")
        return value
    return parse_amount(str(value))


def clean_fields(fields, definitions):
    """
    Converts extracted values to what each Paperless custom field type
    accepts. Values that can't be converted are skipped, because Paperless
    rejects the whole update if any one value is invalid.
    """
    cleaned = {}

    for key, value in fields.items():
        definition = definitions.get(key)
        if not definition:
            logging.warning(f"Skipping unknown field: {key}")
            continue

        if value is None:
            continue  # the model found no value
        data_type = definition["data_type"]
        text = str(value).strip()
        if not text:
            continue

        try:
            if data_type == "date":
                value = parse_date(text)
            elif data_type == "monetary":
                value = f"{to_number(value):.2f}"
            elif data_type == "float":
                value = float(to_number(value))
            elif data_type == "integer":
                number = to_number(value)
                value = number if isinstance(number, int) else int(round(number))
            elif data_type == "boolean":
                lowered = text.lower()
                if lowered in ("true", "yes", "1"):
                    value = True
                elif lowered in ("false", "no", "0"):
                    value = False
                else:
                    raise ValueError("not a yes/no value")
            elif data_type in ("string", "url"):
                if len(text) > MAX_TEXT_LENGTH:
                    logging.warning(
                        f"Value for '{key}' is {len(text)} characters; "
                        f"shortening it to {MAX_TEXT_LENGTH}."
                    )
                value = truncate_text(text)
            else:
                # select, documentlink and other types need IDs, not free text
                logging.warning(
                    f"Skipping '{key}': {data_type} fields aren't supported."
                )
                continue
        except (ValueError, OverflowError):
            # Not the exception text: it can quote the value from the document
            logging.warning(f"Skipping '{key}': not a valid {data_type} value.")
            continue

        cleaned[key] = value

    return cleaned


def fillable_fields(definitions):
    """Returns the definitions whose type the model can fill (see SCHEMA_TYPES)."""
    return {k: d for k, d in definitions.items() if d["data_type"] in SCHEMA_TYPES}


def reply_schema(definitions):
    """
    Builds the strict JSON schema for the reply: a title and one nullable
    value per fillable custom field.

    Strict mode requires every property, so a missing value is null.
    """
    fields = fillable_fields(definitions)
    return {
        "name": "document_metadata",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "fields"],
            "properties": {
                "title": {"type": "string"},
                "fields": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(fields),
                    "properties": {
                        key: dict(SCHEMA_TYPES[d["data_type"]])
                        for key, d in fields.items()
                    },
                },
            },
        },
    }


def build_prompt(ocr_text):
    """
    Builds the user message: just the document text.

    The fields and their types come from the reply schema.
    """
    return f"Document OCR text:\n<<<\n{ocr_text[:MAX_OCR_CHARS]}\n>>>"


def build_update(document, title, cleaned, definitions):
    """
    Builds the PATCH body for the title and custom fields.

    Paperless replaces the whole custom field list on PATCH, so the
    document's existing values are kept and new values override them.
    """
    values = {cf["field"]: cf["value"] for cf in document.get("custom_fields") or []}
    for key, value in cleaned.items():
        values[definitions[key]["id"]] = value

    changes = {}
    if title:
        changes["title"] = title
    if cleaned:
        changes["custom_fields"] = [
            {"field": field_id, "value": value} for field_id, value in values.items()
        ]
    return changes


def apply_metadata(paperless, ai, document):
    """Generates a title and custom field values and saves them."""
    doc_id = document["id"]
    definitions = field_definitions(paperless.custom_fields())

    reply = ai.ask_json(
        SYSTEM_MESSAGE,
        build_prompt(document.get("content") or ""),
        schema=reply_schema(definitions),
    )
    fields = reply.get("fields") or {}
    if not isinstance(fields, dict):
        raise AIError("The reply's 'fields' is not an object.")

    title = truncate_text(str(reply.get("title") or "").strip())
    if not title:
        logging.warning(f"Document {doc_id}: no title returned; keeping the title.")
    cleaned = clean_fields(fields, definitions)

    changes = build_update(document, title, cleaned, definitions)
    if changes:
        paperless.update_document(doc_id, changes)
    logging.info(
        f"Document {doc_id}: title {'set' if title else 'unchanged'}, "
        f"{len(cleaned)} custom field(s) set."
    )
    return MetadataResult(title_set=bool(title), fields_set=len(cleaned))
