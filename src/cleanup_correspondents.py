#!/usr/bin/env python3
"""
Renames correspondents whose name is a leaked JSON reply.

An old bug saved replies such as ``{"correspondent": "ESB Networks"}`` as
the correspondent's name. This script renames each one to the name inside
the JSON. It reports what it would change unless you pass ``--apply``.

Usage:
    cleanup_correspondents.py [--apply]
"""

import argparse
import json
import logging
import sys

from postprocessing.cli import EXIT_OK, build_clients, run


def parse_args(argv=None):
    """Parses the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument(
        "--apply", action="store_true", help="rename them (default: report only)"
    )
    return parser.parse_args(argv)


def name_from_json(name):
    """Returns the real name inside a JSON-blob name, or None."""
    try:
        data = json.loads(name)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(data, dict):
        real_name = str(data.get("correspondent") or "").strip()
        return real_name or None
    return None


def main(argv=None):
    """Finds JSON-blob correspondent names and renames them."""
    args = parse_args(argv)
    paperless, _ = build_clients(require_openai=False)

    renames = []
    for correspondent in paperless.list_all("correspondents/"):
        new_name = name_from_json(correspondent["name"])
        if new_name:
            renames.append((correspondent, new_name))

    for correspondent, new_name in renames:
        action = "Renaming" if args.apply else "Would rename"
        # The new name comes from a model reply, so log only its length
        logging.info(
            f"{action} correspondent {correspondent['id']} "
            f"(new name: {len(new_name)} characters)."
        )
        if args.apply:
            paperless.update_correspondent(correspondent["id"], {"name": new_name})

    if renames and not args.apply:
        logging.info("Nothing changed. Run again with --apply to rename them.")
    logging.info(f"Found {len(renames)} correspondent(s) with JSON names.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(run(main))
