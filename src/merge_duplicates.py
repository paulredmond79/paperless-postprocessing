#!/usr/bin/env python3
import os
import logging
import requests
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Global variables for API configuration
paperless_url = os.getenv("PAPERLESS_URL", "http://localhost:8000")
paperless_token = os.getenv("PAPERLESS_API_TOKEN")

headers = {
    "Authorization": f"Token {paperless_token}",
    "Content-Type": "application/json"
}

def fetch_all_correspondents():
    """
    Fetches all correspondents from Paperless-ngx.
    """
    logging.info("Fetching all correspondents from Paperless-ngx.")
    correspondents = []
    next_url = f"{paperless_url}/api/correspondents/"

    while next_url:
        response = requests.get(next_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        correspondents.extend(data.get("results", []))
        next_url = data.get("next")

    logging.info(f"Fetched {len(correspondents)} correspondents.")
    return correspondents

def fetch_documents_by_correspondent(correspondent_id):
    """
    Fetches all documents associated with a given correspondent ID.
    """
    logging.info(f"Fetching documents for correspondent ID {correspondent_id}.")
    documents = []
    next_url = f"{paperless_url}/api/documents/?correspondent__id={correspondent_id}"

    while next_url:
        response = requests.get(next_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        documents.extend(data.get("results", []))
        next_url = data.get("next")

    logging.info(f"Fetched {len(documents)} documents for correspondent ID {correspondent_id}.")
    return documents

def update_document_correspondent(doc_id, new_correspondent_id):
    """
    Updates the correspondent of a document.
    """
    logging.info(f"Updating document ID {doc_id} to correspondent ID {new_correspondent_id}.")
    url = f"{paperless_url}/api/documents/{doc_id}/"
    payload = {"correspondent": new_correspondent_id}
    response = requests.patch(url, headers=headers, json=payload)
    response.raise_for_status()
    logging.info(f"Document ID {doc_id} updated successfully.")

def update_correspondent_name(correspondent_id, new_name):
    """
    Updates the name of a correspondent.
    """
    logging.info(f"Updating correspondent ID {correspondent_id} with new name: {new_name}.")
    url = f"{paperless_url}/api/correspondents/{correspondent_id}/"
    payload = {"name": new_name}
    response = requests.patch(url, headers=headers, json=payload)
    response.raise_for_status()
    logging.info(f"Correspondent ID {correspondent_id} updated successfully.")

def main():
    logging.info("Starting duplicate correspondent cleanup.")

    # Fetch all correspondents
    correspondents = fetch_all_correspondents()

    # Group correspondents by name (case insensitive)
    grouped = defaultdict(list)
    for correspondent in correspondents:
        grouped[correspondent["name"].strip().lower()].append(correspondent)

    for name, group in grouped.items():
        if len(group) > 1:
            logging.info(f"Found duplicates for name '{name}': {[c['id'] for c in group]}.")

            # Sort by ID to find the oldest correspondent
            group.sort(key=lambda c: c["id"])
            oldest = group[0]

            # Merge documents from all duplicates into the oldest correspondent
            for correspondent in group[1:]:
                documents = fetch_documents_by_correspondent(correspondent["id"])
                for document in documents:
                    update_document_correspondent(document["id"], oldest["id"])

            # Delete duplicate correspondents
            for correspondent in group[1:]:
                logging.info(f"Deleting duplicate correspondent ID {correspondent['id']}.")
                url = f"{paperless_url}/api/correspondents/{correspondent['id']}/"
                response = requests.delete(url, headers=headers)
                response.raise_for_status()
                logging.info(f"Deleted duplicate correspondent ID {correspondent['id']}.")

            # Update the name of the oldest correspondent to title case if needed
            title_case_name = oldest["name"].title()
            if oldest["name"] != title_case_name:
                update_correspondent_name(oldest["id"], title_case_name)

    logging.info("Duplicate correspondent cleanup completed.")

if __name__ == "__main__":
    main()
