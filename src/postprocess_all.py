#!/usr/bin/env python3
"""
Runs post-processing on every document that hasn't been through it yet.

"Not yet processed" means the document lacks the ``gpt-correspondent`` tag.
By default only the correspondent step runs; pass ``--with-metadata`` to
also regenerate titles and custom fields. Each document costs one or two
paid OpenAI calls, so try ``--limit`` first.

A failing document is logged and the batch carries on. Exits 1 at the end
if any document failed.

Usage:
    postprocess_all.py [--with-metadata] [--limit N]
"""

import argparse
import logging
import sys

from postprocessing.cli import EXIT_FAILED, EXIT_OK, build_clients, run
from postprocessing.correspondent import PROCESSED_TAG
from postprocessing.pipeline import process_document


def non_negative_int(text):
    """argparse type for a whole number that is 0 or more."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number: {text!r}")
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def parse_args(argv=None):
    """Parses the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument(
        "--with-metadata",
        action="store_true",
        help="also generate titles and fill custom fields",
    )
    parser.add_argument(
        "--limit", type=non_negative_int, help="process at most this many documents"
    )
    return parser.parse_args(argv)


def unprocessed_document_ids(paperless):
    """Returns the IDs of documents without the gpt-correspondent tag."""
    tag = paperless.tags_by_name().get(PROCESSED_TAG)
    params = {"tags__id__none": tag["id"]} if tag else {}
    return [doc["id"] for doc in paperless.list_documents(params)]


def main(argv=None):
    """Processes every unprocessed document and returns an exit code."""
    args = parse_args(argv)
    paperless, ai = build_clients()
    steps = ["correspondent", "metadata"] if args.with_metadata else ["correspondent"]

    doc_ids = unprocessed_document_ids(paperless)
    if args.limit is not None:
        doc_ids = doc_ids[: args.limit]
    logging.info(f"Processing {len(doc_ids)} document(s): {', '.join(steps)}.")

    failed = [
        doc_id
        for doc_id in doc_ids
        if not process_document(paperless, ai, doc_id, steps)
    ]

    if failed:
        logging.error(f"{len(failed)} document(s) failed: {failed}")
        return EXIT_FAILED
    logging.info("All documents processed.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(run(main))
