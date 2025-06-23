import logging
import re

import requests


# Tag Management Functions
def fetch_tags(api_url, headers):
    """
    Fetches all tags from the API and returns a dictionary of tag names to their IDs.
    """
    try:
        response = requests.get(f"{api_url}/api/tags/", headers=headers)
        response.raise_for_status()
        tags = {tag["name"]: tag["id"] for tag in response.json().get("results", [])}
        logging.debug(f"Fetched tags: {tags}")
        return tags
    except Exception as e:
        logging.error(f"Failed to fetch tags: {e}")
        return {}


def create_tag(api_url, headers, name):
    """
    Creates a new tag with the given name and returns its ID.
    """
    logging.info(f"Creating new tag: {name}")
    payload = {"name": name}
    logging.debug(f"Payload for creating tag: {payload}")
    try:
        response = requests.post(f"{api_url}/api/tags/", headers=headers, json=payload)
        logging.debug(f"Response status code: {response.status_code}")
        logging.debug(f"Response content: {response.text}")
        response.raise_for_status()
        tag = response.json()
        logging.info(f"Tag '{name}' created successfully with ID: {tag['id']}")
        return tag["id"]
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error occurred while creating tag '{name}': {e}")
        logging.error(f"Response content: {response.text}")
        return None
    except Exception as e:
        logging.error(f"Failed to create tag '{name}': {e}")
        return None


def fetch_or_create_tag(api_url, headers, tag_name):
    """
    Ensures a tag exists by either fetching it or creating it if it doesn't exist.
    Returns the tag ID.
    """
    try:
        tags = fetch_tags(api_url, headers)
        # Normalize tag names to lowercase and strip whitespace for comparison
        normalized_tags = {
            name.lower().strip(): tag_id for name, tag_id in tags.items()
        }
        tag_id = normalized_tags.get(tag_name.lower().strip())
        if not tag_id:
            logging.info(f"Tag '{tag_name}' not found. Creating it.")
            tag_id = create_tag(api_url, headers, tag_name)
            if not tag_id:
                raise Exception(f"Failed to create tag '{tag_name}'.")
        return tag_id
    except Exception as e:
        logging.error(f"Failed to fetch or create tag '{tag_name}': {e}")
        raise


def add_tag_to_document(api_url, headers, document_id, tag_id):
    """
    Adds a tag to a document by its ID.
    """
    try:
        current = fetch_document_details(api_url, headers, document_id)
        existing_tags = {
            tag.get("id") if isinstance(tag, dict) else tag
            for tag in current.get("tags", [])
        }
        existing_tags.add(tag_id)

        doc_url = f"{api_url}/api/documents/{document_id}/"
        payload = {"tags": sorted(existing_tags)}
        response = requests.patch(doc_url, headers=headers, json=payload)
        response.raise_for_status()
        if response.status_code != 200:
            raise Exception(f"Failed to add tag {tag_id} to document {document_id}.")
        logging.info(f"Successfully added tag to document {document_id}.")
    except Exception as e:
        logging.error(f"Failed to add tag to document {document_id}: {e}")
        raise Exception(f"Failed to add tag {tag_id} to document {document_id}.") from e


# Correspondent Management Functions
def fetch_correspondents(api_url, headers):
    """
    Fetches all correspondents from the API and returns a dictionary of correspondent names to their IDs.
    """
    try:
        response = requests.get(f"{api_url}/api/correspondents/", headers=headers)
        response.raise_for_status()
        return {
            correspondent["name"]: correspondent["id"]
            for correspondent in response.json().get("results", [])
        }
    except Exception as e:
        logging.error(f"Failed to fetch correspondents: {e}")
        return {}


def create_correspondent(api_url, headers, name):
    """
    Creates a new correspondent with the given name and returns its ID.
    """
    try:
        response = requests.post(
            f"{api_url}/api/correspondents/", headers=headers, json={"name": name}
        )
        response.raise_for_status()
        return response.json().get("id")
    except Exception as e:
        logging.error(f"Failed to create correspondent '{name}': {e}")
        return None


def get_correspondents(api_url, headers):
    """
    Fetches all correspondents from the API and returns a dictionary of correspondent names to their IDs.
    """
    try:
        response = requests.get(f"{api_url}/api/correspondents/", headers=headers)
        response.raise_for_status()
        return {
            correspondent["name"]: correspondent["id"]
            for correspondent in response.json().get("results", [])
        }
    except Exception as e:
        logging.error(f"Failed to fetch correspondents: {e}")
        return {}


# Document Management Functions
def fetch_document_details(api_url, headers, doc_id):
    """
    Fetches the details of a document by its ID.
    """
    try:
        logging.info(f"Fetching details for document ID: {doc_id}.")
        doc_url = f"{api_url}/api/documents/{doc_id}/"
        response = requests.get(doc_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to fetch document details for ID {doc_id}: {e}")
        raise


def update_document_metadata(api_url, headers, doc_id, payload):
    """
    Updates the metadata of a document by its ID.
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


# Custom Field Management Functions
def fetch_custom_fields(api_url, headers):
    """
    Fetches all custom fields from the API and returns a dictionary of field names to their metadata.
    """
    try:
        logging.info("Fetching custom fields metadata.")
        response = requests.get(f"{api_url}/api/custom_fields/", headers=headers)
        response.raise_for_status()
        return {
            to_snake_case(item["name"]): {
                "id": item["id"],
                "data_type": item["data_type"],
            }
            for item in response.json().get("results", [])
        }
    except Exception as e:
        logging.error(f"Failed to fetch custom fields metadata: {e}")
        raise


def ensure_custom_field_exists(
    api_url, headers, field_name, data_type="string", extra_data=None
):
    """
    Ensures a custom field exists by either fetching it or creating it if it doesn't exist.
    Returns the custom field metadata.
    """
    try:
        query_url = f"{api_url}/api/custom_fields/?name__iexact={field_name}"
        response = requests.get(query_url, headers=headers)
        response.raise_for_status()
        results = response.json().get("results", [])

        if results:
            logging.info(f"Custom field '{field_name}' already exists.")
            return results[0]

        logging.info(
            f"Creating custom field '{field_name}' with data type '{data_type}'."
        )
        create_url = f"{api_url}/api/custom_fields/"
        payload = {
            "name": field_name,
            "data_type": data_type,
            "extra_data": extra_data or {},
        }
        response = requests.post(create_url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to ensure custom field '{field_name}': {e}")
        raise Exception(f"Failed to ensure custom field '{field_name}'.") from e


# Utility Functions
def to_snake_case(text):
    """
    Converts a given text to snake_case.
    """
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def fetch_ocr_data(api_url, headers, doc_id):
    """
    Fetches the OCR data of a document by its ID.
    """
    try:
        logging.info(f"Fetching OCR data for document ID: {doc_id}")
        doc_url = f"{api_url}/api/documents/{doc_id}/"
        response = requests.get(doc_url, headers=headers)
        response.raise_for_status()
        ocr_data = response.json().get("content", "")
        logging.debug(f"OCR data response: {ocr_data}")
        logging.info(f"OCR data fetched successfully for document ID: {doc_id}")
        return ocr_data
    except Exception as e:
        logging.error(f"Failed to fetch OCR data for document ID {doc_id}: {e}")
        raise Exception(f"Failed to fetch OCR data for document ID {doc_id}.") from e
