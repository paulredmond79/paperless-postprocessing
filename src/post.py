#!/usr/bin/env python3
"""
Post-processes one Paperless document: the post-consume hook entry point.

Runs every step in order:

1. correspondent: chooses the correspondent with OpenAI, creates it if new,
   assigns it, and tags the document ``gpt-correspondent``
2. metadata: generates a title and fills the custom fields

A failing step is logged and the next one still runs. Exits 0 when every
step succeeded, 1 when any failed and 2 when a setting is missing.

Usage:
    post.py <document_id> [--only correspondent|metadata]

Paperless sets ``DOCUMENT_ID`` for post-consume hooks, so the ID can also
come from there.
"""

import argparse
import os
import sys

from postprocessing.cli import EXIT_FAILED, EXIT_OK, build_clients, run
from postprocessing.pipeline import STEPS, process_document


def parse_args(argv=None):
    """Parses the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument(
        "document_id",
        nargs="?",
        default=os.getenv("DOCUMENT_ID"),
        help="Paperless document ID (defaults to $DOCUMENT_ID)",
    )
    parser.add_argument(
        "--only",
        choices=list(STEPS),
        help="run just this step",
    )
    args = parser.parse_args(argv)
    if not args.document_id:
        parser.error("a document ID is required (argument or $DOCUMENT_ID)")
    if not str(args.document_id).isdigit():
        parser.error(f"document ID must be a number, got {args.document_id!r}")
    return args


def main(argv=None):
    """Runs the requested steps on one document and returns an exit code."""
    args = parse_args(argv)
    paperless, ai = build_clients()
    steps = [args.only] if args.only else list(STEPS)
    ok = process_document(paperless, ai, int(args.document_id), steps)
    return EXIT_OK if ok else EXIT_FAILED


if __name__ == "__main__":
    sys.exit(run(main))
