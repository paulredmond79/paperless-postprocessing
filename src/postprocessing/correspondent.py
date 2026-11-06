"""Choosing and assigning a document's correspondent with OpenAI."""

import logging
from dataclasses import dataclass
from typing import Optional

from postprocessing.ai import AIError

PROCESSED_TAG = "gpt-correspondent"
UNDETERMINED_TAG = "gpt-correspondent-unable-to-determine"

# Some models answer with this sentence instead of a "no_match" status
UNCLEAR_PHRASE = "the ocr text does not provide a clear correspondent name."

# The start of a document (letterhead, sender) is what identifies it
MAX_OCR_CHARS = 4000
MAX_CORRESPONDENTS = 500

# The instructions are fixed and come first; only the user message varies
SYSTEM_MESSAGE = """\
You identify the correspondent of documents in a personal document archive \
(Paperless-ngx) for a household in Ireland.

The correspondent is the organisation or person that sent or issued the \
document. It is never the person or household the document is addressed to.

Rules:
1. Prefer the organisation over an individual who works for it. For example, \
choose "Goatstown Medical Centre", not the doctor who signed the letter.
2. If one of the existing correspondents is the same organisation, return \
status "match" with its name copied exactly as listed. That includes the same \
organisation under a different spelling, abbreviation, brand or department, \
for example "Revenue" for "Office of the Revenue Commissioners".
3. Only if none of them fits, return status "suggest_new" with the \
organisation's usual short name as printed on the document. Leave out \
addresses, departments, branches and reference numbers.
4. If the text doesn't show who sent the document, return status "no_match" \
with correspondent null. Don't guess from the recipient's name or from \
companies that are only mentioned in passing, such as payment methods.

The OCR text may contain recognition errors."""

REPLY_SCHEMA = {
    "name": "correspondent",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "correspondent"],
        "properties": {
            "status": {"type": "string", "enum": ["match", "suggest_new", "no_match"]},
            "correspondent": {
                "type": ["string", "null"],
                "description": "The correspondent's name, or null for no_match.",
            },
        },
    },
}


@dataclass
class CorrespondentResult:
    """What the correspondent step did to a document."""

    status: str  # "assigned", "unchanged" or "undetermined"
    name: Optional[str] = None


def build_prompt(ocr_text, correspondent_names):
    """
    Builds the user message: the existing correspondents, then the document.

    Names go one per line because some contain commas.
    """
    names = sorted(correspondent_names, key=str.lower)[:MAX_CORRESPONDENTS]
    listed = "\n".join(f"- {name}" for name in names) or "(none yet)"
    return (
        f"Existing correspondents:\n{listed}\n\n"
        f"Document OCR text:\n<<<\n{ocr_text[:MAX_OCR_CHARS]}\n>>>"
    )


def choose_correspondent(ai, ocr_text, correspondent_names):
    """
    Asks OpenAI for the correspondent's name.

    Returns the name, or None when the model can't tell. Raises AIError for
    a reply in the wrong shape.
    """
    reply = ai.ask_json(
        SYSTEM_MESSAGE,
        build_prompt(ocr_text, correspondent_names),
        schema=REPLY_SCHEMA,
    )
    status = reply.get("status")

    if status == "no_match":
        return None
    if status not in ("match", "suggest_new"):
        raise AIError(f"Unexpected status in the reply: {status!r}")

    name = str(reply.get("correspondent") or "").strip()
    if not name:
        raise AIError(f"The reply has status {status!r} but no correspondent.")
    if name.lower() == UNCLEAR_PHRASE:
        return None
    return name


def detect_correspondent(paperless, ai, document):
    """
    Chooses the document's correspondent and saves it.

    When a correspondent is found, it is created if new, assigned if
    different, and the document is tagged ``gpt-correspondent``. When none
    can be found, the document is tagged
    ``gpt-correspondent-unable-to-determine`` instead.
    """
    doc_id = document["id"]
    correspondents = paperless.correspondents_by_name()
    names = [c["name"] for c in correspondents.values()]

    name = choose_correspondent(ai, document.get("content") or "", names)

    if name is None:
        logging.warning(f"Document {doc_id}: couldn't determine a correspondent.")
        tag = paperless.get_or_create_tag(UNDETERMINED_TAG)
        paperless.add_tags(doc_id, [tag["id"]])
        return CorrespondentResult("undetermined")

    correspondent = correspondents.get(
        name.lower()
    ) or paperless.get_or_create_correspondent(name)

    if document.get("correspondent") == correspondent["id"]:
        status = "unchanged"
        logging.info(
            f"Document {doc_id}: correspondent is already {correspondent['id']}."
        )
    else:
        status = "assigned"
        paperless.update_document(doc_id, {"correspondent": correspondent["id"]})
        logging.info(f"Document {doc_id}: correspondent set to {correspondent['id']}.")

    # Tag every document the AI has checked, so batch runs skip it next time
    tag = paperless.get_or_create_tag(PROCESSED_TAG)
    paperless.add_tags(doc_id, [tag["id"]])
    return CorrespondentResult(status, correspondent["name"])
