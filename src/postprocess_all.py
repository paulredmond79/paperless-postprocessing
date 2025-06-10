#!/usr/bin/env python3
import logging
import os
import sys

import requests

from postprocess import fetch_tags
from postprocess import main as process_document

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Global variables for API configuration
paperless_url = os.getenv("PAPERLESS_URL", "http://localhost:8000")
paperless_token = os.getenv("PAPERLESS_API_TOKEN")

headers = {
    "Authorization": f"Token {paperless_token}",
    "Content-Type": "application/json",
}


def fetch_all_documents():
    """
    Fetches all documents from Paperless-ngx.
    """
    logging.info("Fetching all documents from Paperless-ngx.")
    documents = []
    next_url = f"{paperless_url}/api/documents/"

    while next_url:
        response = requests.get(next_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        documents.extend(data.get("results", []))
        next_url = data.get("next")

    logging.info(f"Fetched {len(documents)} documents.")
    return documents


def main():
    logging.info(
        "Starting post-processing for all documents without the 'gpt-correspondent' tag."
    )

    # Fetch all documents
    documents = fetch_all_documents()

    # Fetch existing tags
    tags = fetch_tags()
    gpt_tag = tags.get("gpt-correspondent")

    if not gpt_tag:
        logging.error(
            "The 'gpt-correspondent' tag does not exist. Please create it first."
        )
        sys.exit(1)

    gpt_tag_id = gpt_tag["id"]

    # Process each document
    for document in documents:
        document_id = document["id"]

        # Process tags to handle both integers and dictionaries
        document_tag_ids = set()
        for tag in document.get("tags", []):
            if isinstance(tag, dict):
                tag_id = tag.get("id")
                if tag_id is not None:
                    document_tag_ids.add(tag_id)
            elif isinstance(tag, int):
                document_tag_ids.add(tag)

        # Skip documents that already have the 'gpt-correspondent' tag
        if gpt_tag_id in document_tag_ids:
            logging.info(
                f"Skipping document ID {document_id} as it already has the 'gpt-correspondent' tag."
            )
            continue

        # Process the document
        logging.info(f"Processing document ID {document_id}.")
        process_document(document_id)

    logging.info("Post-processing completed for all documents.")


if __name__ == "__main__":
    main()
