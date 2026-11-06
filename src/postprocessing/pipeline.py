"""Runs the post-processing steps on one document."""

import logging

from postprocessing.ai import AIError
from postprocessing.correspondent import detect_correspondent
from postprocessing.metadata import apply_metadata
from postprocessing.paperless import PaperlessError

# Every step, in the order they run
STEPS = {
    "correspondent": detect_correspondent,
    "metadata": apply_metadata,
}


def process_document(paperless, ai, doc_id, steps=tuple(STEPS)):
    """
    Runs the given steps on one document and returns True if all succeeded.

    A failing step is logged and the next step still runs, so a problem
    with custom fields doesn't stop the correspondent being set. A document
    with no OCR text is skipped and counts as success.
    """
    try:
        document = paperless.get_document(doc_id)
    except PaperlessError as e:
        logging.error(f"Document {doc_id}: couldn't fetch it: {e}")
        return False

    if not (document.get("content") or "").strip():
        logging.warning(f"Document {doc_id}: no OCR text, so nothing to do.")
        return True

    ok = True
    for step in steps:
        try:
            STEPS[step](paperless, ai, document)
        except (PaperlessError, AIError) as e:
            logging.error(f"Document {doc_id}: {step} step failed: {e}")
            ok = False
    return ok
