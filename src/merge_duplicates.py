#!/usr/bin/env python3
"""
Merges correspondents whose names differ only by case or spacing.

For each group of duplicates, the oldest correspondent (lowest ID) is kept.
Documents are moved to it and the other correspondents are DELETED, which
can't be undone. The script reports what it would change unless you pass
``--apply``.

Usage:
    merge_duplicates.py [--apply]
"""

import argparse
import logging
import sys
from collections import defaultdict

from postprocessing.cli import EXIT_OK, build_clients, run


def parse_args(argv=None):
    """Parses the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument(
        "--apply",
        action="store_true",
        help="move documents and delete duplicates (default: report only)",
    )
    return parser.parse_args(argv)


def duplicate_groups(correspondents):
    """
    Groups correspondents by normalised name.

    Returns a list of groups with more than one member, each sorted oldest
    first.
    """
    groups = defaultdict(list)
    for correspondent in correspondents:
        key = " ".join(correspondent["name"].split()).lower()
        groups[key].append(correspondent)
    return [
        sorted(group, key=lambda c: c["id"])
        for group in groups.values()
        if len(group) > 1
    ]


def main(argv=None):
    """Finds duplicate correspondents and merges them."""
    args = parse_args(argv)
    paperless, _ = build_clients(require_openai=False)

    groups = duplicate_groups(paperless.list_all("correspondents/"))
    for keep, *duplicates in groups:
        for duplicate in duplicates:
            documents = paperless.list_documents({"correspondent__id": duplicate["id"]})
            logging.info(
                f"{'Merging' if args.apply else 'Would merge'} correspondent "
                f"{duplicate['id']} ('{duplicate['name']}', {len(documents)} "
                f"document(s)) into {keep['id']} ('{keep['name']}')."
            )
            if not args.apply:
                continue
            for document in documents:
                paperless.update_document(document["id"], {"correspondent": keep["id"]})
            paperless.delete_correspondent(duplicate["id"])

    if groups and not args.apply:
        logging.info("Nothing changed. Run again with --apply to merge them.")
    logging.info(f"Found {len(groups)} group(s) of duplicate correspondents.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(run(main))
