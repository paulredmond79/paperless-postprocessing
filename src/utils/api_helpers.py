import logging
import re

import requests


def get_correspondents(api_url, headers):
    try:
        response = requests.get(f"{api_url}/api/correspondents/", headers=headers)
        response.raise_for_status()
        return {
            correspondent["name"]: correspondent["id"]
            for correspondent in response.json().get("results", [])
        }
    except Exception as e:
        print(f"❌ Failed to fetch correspondents: {e}")
        return {}


def create_correspondent(api_url, headers, name):
    try:
        response = requests.post(
            f"{api_url}/api/correspondents/", headers=headers, json={"name": name}
        )
        response.raise_for_status()
        return response.json().get("id")
    except Exception as e:
        print(f"❌ Failed to create correspondent '{name}': {e}")
        return None


def get_tags(api_url, headers):
    try:
        response = requests.get(f"{api_url}/api/tags/", headers=headers)
        response.raise_for_status()
        return {tag["name"]: tag["id"] for tag in response.json().get("results", [])}
    except Exception as e:
        print(f"❌ Failed to fetch tags: {e}")
        return {}


def create_tag(api_url, headers, name):
    try:
        response = requests.post(
            f"{api_url}/api/tags/", headers=headers, json={"name": name}
        )
        response.raise_for_status()
        return response.json().get("id")
    except Exception as e:
        print(f"❌ Failed to create tag '{name}': {e}")
        return None


def add_tag_to_document(api_url, headers, document_id, tag_id):
    try:
        current = fetch_document_details(api_url, headers, document_id)
        existing_tags = set()
        for tag in current.get("tags", []):
            if isinstance(tag, dict):
                tid = tag.get("id")
                if tid is not None:
                    existing_tags.add(tid)
            elif isinstance(tag, int):
                existing_tags.add(tag)

        existing_tags.add(tag_id)

        doc_url = f"{api_url}/api/documents/{document_id}/"
        payload = {"tags": sorted(existing_tags)}
        response = requests.patch(doc_url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"✅ Successfully added tag to document {document_id}.")
    except Exception as e:
        print(f"❌ Failed to add tag to document {document_id}: {e}")


def fetch_document_details(api_url, headers, doc_id):
    """
    Fetches the document details, including its current correspondent and tags.
    """
    try:
        logging.info(f"Fetching details for document ID: {doc_id}.")
        doc_url = f"{api_url}/api/documents/{doc_id}/"
        response = requests.get(doc_url, headers=headers)
        response.raise_for_status()
        document_details = response.json()
        logging.debug(f"Document details: {document_details}")
        return document_details
    except Exception as e:
        logging.error(f"Failed to fetch document details for ID {doc_id}: {e}")
        raise


def update_document_metadata(api_url, headers, doc_id, payload):
    """
    Updates the document metadata, including title and custom fields.
    """
    try:
        logging.info(f"Updating metadata for document ID: {doc_id}.")
        doc_url = f"{api_url}/api/documents/{doc_id}/"
        response = requests.patch(doc_url, headers=headers, json=payload)
        response.raise_for_status()
        logging.info(f"Successfully updated document {doc_id}.")
    except Exception as e:
        logging.error(f"Failed to update document metadata for ID {doc_id}: {e}")
        raise


def fetch_custom_fields(api_url, headers):
    """
    Fetches the custom fields metadata from the Paperless-ngx API.
    """
    try:
        logging.info("Fetching custom fields metadata.")
        response = requests.get(f"{api_url}/api/custom_fields/", headers=headers)
        response.raise_for_status()
        data = response.json().get("results", [])
        return {
            to_snake_case(item["name"]): {
                "id": item["id"],
                "data_type": item["data_type"],
            }
            for item in data
        }
    except Exception as e:
        logging.error(f"Failed to fetch custom fields metadata: {e}")
        raise


def to_snake_case(text):
    """
    Converts a given text to snake_case.
    """
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
