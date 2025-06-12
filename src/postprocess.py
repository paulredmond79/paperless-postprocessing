#!/usr/bin/env python3
import json
import logging
import os
import sys

import requests
from openai import OpenAI

from utils.api_helpers import fetch_ocr_data, fetch_or_create_tag

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Global variables for API configuration
paperless_url = os.getenv("PAPERLESS_URL", "http://localhost:8000")
paperless_token = os.getenv("PAPERLESS_API_TOKEN")
openai_api_key = os.getenv("OPENAI_API_KEY")

headers = {
    "Authorization": f"Token {paperless_token}",
    "Content-Type": "application/json",
}


def fetch_correspondents():
    """
    Fetches existing correspondents as a dictionary keyed by name.
    """
    logging.info("Fetching existing correspondents from Paperless-ngx.")
    correspondents = {}
    next_url = f"{paperless_url}/api/correspondents/"

    while next_url:
        response = requests.get(next_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        for c in data.get("results", []):
            correspondents[c["name"].lower()] = c
        next_url = data.get("next")

    logging.debug(f"Fetched correspondents: {correspondents}")
    logging.info(f"Fetched {len(correspondents)} correspondents.")
    return correspondents


def create_correspondent(name):
    """
    Creates a correspondent and returns the API response.
    """
    logging.info(f"Creating new correspondent: {name}")
    payload = {"name": name}
    logging.debug(f"Payload for creating correspondent: {payload}")
    try:
        response = requests.post(
            f"{paperless_url}/api/correspondents/", headers=headers, json=payload
        )
        response.raise_for_status()
        correspondent = response.json()
        logging.debug(f"Response for created correspondent: {correspondent}")
        logging.info(
            f"Correspondent '{name}' created successfully with ID: {correspondent['id']}"
        )
        return correspondent
    except requests.exceptions.HTTPError:
        if response.status_code == 400:
            logging.error(
                f"Failed to create correspondent '{name}'. Response: {response.text}"
            )
            if "already exists" in response.text.lower():
                logging.warning(
                    f"Correspondent '{name}' already exists. Fetching existing correspondent."
                )
                correspondents = fetch_correspondents()
                return correspondents.get(name.lower())
            elif "violates owner / name unique constraint" in response.text.lower():
                logging.warning(
                    f"Correspondent '{name}' violates unique constraint. Searching for existing correspondent."
                )
                correspondents = fetch_correspondents()
                existing_correspondent = correspondents.get(name.lower())
                if existing_correspondent:
                    logging.info(
                        f"Found existing correspondent '{name}' with ID: {existing_correspondent['id']}."
                    )
                    return existing_correspondent
                else:
                    logging.error(
                        f"Correspondent '{name}' not found despite unique constraint violation."
                    )
                    raise
        raise


def fetch_tags():
    """
    Fetches existing tags as a dictionary keyed by name.
    """
    logging.info("Fetching existing tags from Paperless-ngx.")
    response = requests.get(f"{paperless_url}/api/tags/", headers=headers)
    response.raise_for_status()
    tags = {tag["name"].lower(): tag for tag in response.json().get("results", [])}
    logging.debug(f"Fetched tags: {tags}")
    logging.info(f"Fetched {len(tags)} tags.")
    return tags


def create_tag(name):
    """
    Creates a tag and returns the API response.
    """
    logging.info(f"Creating new tag: {name}")
    payload = {"name": name}
    logging.debug(f"Payload for creating tag: {payload}")
    response = requests.post(
        f"{paperless_url}/api/tags/", headers=headers, json=payload
    )
    response.raise_for_status()
    tag = response.json()
    logging.debug(f"Response for created tag: {tag}")
    logging.info(f"Tag '{name}' created successfully with ID: {tag['id']}")
    return tag


def add_tag_to_document(doc_id, tag_id):
    """
    Adds a tag to a document if it is not already present.
    """
    logging.info(f"Adding tag ID {tag_id} to document ID {doc_id}.")
    current = fetch_document_details(doc_id)

    existing_tags = set()
    for tag in current.get("tags", []):
        if isinstance(tag, dict):
            tag_id_value = tag.get("id")
            if tag_id_value is not None:
                existing_tags.add(tag_id_value)
        elif isinstance(tag, int):
            existing_tags.add(tag)

    existing_tags.add(tag_id)

    doc_url = f"{paperless_url}/api/documents/{doc_id}/"
    payload = {"tags": sorted(existing_tags)}
    logging.debug(f"Payload for adding tag to document: {payload}")
    response = requests.patch(doc_url, headers=headers, json=payload)
    response.raise_for_status()
    logging.info(f"Tag ID {tag_id} added to document ID {doc_id} successfully.")


def determine_correspondent_with_openai(ocr_data, correspondents):
    """
    Uses OpenAI to guess the correspondent from OCR text.
    """
    logging.info("Determining correspondent using OpenAI.")
    client = OpenAI(api_key=openai_api_key)

    # Limit the number of correspondents to include in the prompt
    max_correspondents = 50
    truncated_correspondents = list(correspondents.keys())[:max_correspondents]

    # Truncate the OCR text to a manageable length
    max_ocr_length = 1000
    truncated_ocr_data = ocr_data[:max_ocr_length]

    prompt = (
        "You are a document assistant. Based on the OCR text below, determine the "
        "most likely correspondent name.\n\n"
        "The correspondent of a document is the person, institution, or company "
        "that a document originates from. Prefer company names or institution "
        "names over personal names when possible. For example Goatstown Medical "
        "Center over Dr. Rodney Reagan or similar. The correspondent name should "
        "be a clear and identifiable name, not a generic term or phrase.\n\n"
        "There are three scenarios to consider:\n"
        "1. If there is an appropriate match in the list of already existing "
        "correspondents, return the following JSON:\n"
        '   {"status": "match", "correspondent": "<matched_correspondent_name>"}'
        "\n2. If there is no appropriate match in the list of already existing "
        "correspondents but you can determine an appropriate new correspondent, "
        "return the following JSON:\n"
        '   {"status": "suggest_new", "correspondent": "<suggested_correspondent_name>"}'
        "\n3. If there is no appropriate match in the list of already existing "
        "correspondents and you cannot determine one, return the following JSON:\n"
        '   {"status": "no_match", "reason": "Unable to determine a correspondent"}'
        "\n\nExisting correspondents:\n"
        f"{', '.join(truncated_correspondents)}\n\n"
        "OCR Text:\n"
        f"{truncated_ocr_data}\n\n"
        "Return the result as specified above, but double check your response "
        "before you do."
    )

    system_message = (
        "You're a document assistant for metadata extraction. The correspondent "
        "of a document is the person, institution, or company that a document "
        "originates from."
    )
    logging.debug(f"OpenAI prompt: {prompt}")
    try:
        ai_response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        ai_response_content = ai_response.choices[0].message.content.strip()
        logging.debug(f"OpenAI response: {ai_response_content}")

        # Parse the AI response as JSON
        try:
            ai_response_json = json.loads(ai_response_content)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse AI response as JSON: {e}")
            logging.debug(f"AI response content: {ai_response_content}")
            return {"status": "error", "reason": "Invalid JSON from AI"}

        # Validate the structure of the AI response
        if not isinstance(ai_response_json, dict) or "status" not in ai_response_json:
            logging.error(
                "Invalid AI response format. Expected a JSON object with a 'status' key."
            )
            logging.debug(f"AI response content: {ai_response_json}")
            return {"status": "error", "reason": "Invalid JSON structure"}

        return ai_response_json

    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        return {"status": "error", "reason": "OpenAI API error"}


def update_document_correspondent(doc_id, correspondent_id):
    """
    Updates the document's correspondent to the specified correspondent ID.
    """
    logging.info(
        f"Updating document ID {doc_id} with correspondent ID {correspondent_id}."
    )
    doc_url = f"{paperless_url}/api/documents/{doc_id}/"
    payload = {"correspondent": correspondent_id}
    logging.debug(f"Payload for updating document correspondent: {payload}")
    response = requests.patch(doc_url, headers=headers, json=payload)
    logging.debug(f"API response for updating document: {response.json()}")
    response.raise_for_status()
    logging.info(
        f"Document ID {doc_id} updated with correspondent ID {correspondent_id} successfully."
    )


def fetch_document_details(doc_id):
    """
    Fetches the document details, including its current correspondent and tags.
    """
    logging.info(f"Fetching details for document ID: {doc_id}.")
    doc_url = f"{paperless_url}/api/documents/{doc_id}/"
    response = requests.get(doc_url, headers=headers)
    response.raise_for_status()
    document_details = response.json()
    logging.debug(f"Document details: {document_details}")
    return document_details


def main(doc_id):
    """
    Post-processes a single document by ID.
    """
    logging.info(f"Starting post-processing for document ID: {doc_id}")

    # Fetch document details
    document_details = fetch_document_details(doc_id)
    current_correspondent_id = document_details.get("correspondent")

    # Process tags to handle both integers and dictionaries
    current_tags = set()
    for tag in document_details.get("tags", []):
        if isinstance(tag, dict):
            current_tags.add(tag["id"])
        elif isinstance(tag, int):
            current_tags.add(tag)

    # Fetch OCR data
    ocr_data = fetch_ocr_data(paperless_url, headers, doc_id)
    if not ocr_data:
        logging.warning("No OCR content found for document.")
        sys.exit(0)

    # Fetch existing correspondents
    logging.info("Fetching existing correspondents.")
    correspondents = fetch_correspondents()

    # Determine correspondent using OpenAI
    logging.info("Determining the most likely correspondent using OpenAI.")
    ai_response = determine_correspondent_with_openai(ocr_data, correspondents)

    # Handle AI response based on its status
    if ai_response["status"] == "match" or ai_response["status"] == "suggest_new":
        correspondent_name = ai_response.get("correspondent")
        if not correspondent_name:
            logging.error(
                "AI response is missing the 'correspondent' field for status 'match' or 'suggest_new'."
            )
            logging.debug(f"AI response content: {ai_response}")
            sys.exit(1)
    elif ai_response["status"] == "no_match":
        logging.warning(
            "AI could not determine a correspondent. Adding 'gpt-correspondent-unable-to-determine' tag."
        )

        # Fetch or create the 'gpt-correspondent-unable-to-determine' tag
        unable_to_determine_tag_name = "gpt-correspondent-unable-to-determine"
        unable_to_determine_tag = fetch_or_create_tag(
            paperless_url, headers, unable_to_determine_tag_name
        )

        # Add the tag to the document
        if unable_to_determine_tag["id"] not in current_tags:
            add_tag_to_document(doc_id, unable_to_determine_tag["id"])

        return  # Exit without updating the correspondent
    else:
        logging.error(f"Unexpected status in AI response: {ai_response['status']}")
        logging.debug(f"AI response content: {ai_response}")
        sys.exit(1)

    # Fetch the correspondent from the existing list or create a new one
    correspondent = correspondents.get(correspondent_name.lower())

    # Create new correspondent if not found
    if not correspondent:
        logging.info(
            f"No matching correspondent found for '{correspondent_name}'. Creating a new one."
        )
        correspondent = create_correspondent(correspondent_name)

    # Update the document's correspondent only if it differs
    if current_correspondent_id != correspondent["id"]:
        logging.info(
            "Current correspondent ID (%s) differs from determined "
            "correspondent ID (%s). Updating the document.",
            current_correspondent_id,
            correspondent["id"],
        )
        update_document_correspondent(doc_id, correspondent["id"])

        # Fetch tags
        logging.info("Fetching existing tags.")
        tags = fetch_tags()
        tag_name = "gpt-correspondent"
        tag = tags.get(tag_name.lower())

        # Create new tag if not found
        if not tag:
            logging.info(f"No matching tag found for '{tag_name}'. Creating a new one.")
            tag = create_tag(tag_name)

        # Add tag to document only if it is not already present
        if tag["id"] not in current_tags:
            logging.info(
                f"Adding tag '{tag['name']}' (ID: {tag['id']}) "
                f"to document ID {doc_id}."
            )
            add_tag_to_document(doc_id, tag["id"])
    else:
        logging.info(
            "No update needed. Current correspondent ID (%s) matches the "
            "determined correspondent ID (%s).",
            current_correspondent_id,
            correspondent["id"],
        )
        tag = None  # Ensure 'tag' is defined even if no updates are made

    # Check if OpenAI was unable to determine a correspondent
    if (
        correspondent_name.lower()
        == "the ocr text does not provide a clear correspondent name."
    ):
        logging.warning(
            "OpenAI could not determine a correspondent. Adding 'gpt-correspondent-unable-to-determine' tag."
        )

        # Fetch or create the 'gpt-correspondent-unable-to-determine' tag
        unable_to_determine_tag_name = "gpt-correspondent-unable-to-determine"
        unable_to_determine_tag = fetch_or_create_tag(
            paperless_url, headers, unable_to_determine_tag_name
        )

        # Add the tag to the document
        if unable_to_determine_tag["id"] not in current_tags:
            add_tag_to_document(doc_id, unable_to_determine_tag["id"])

        return  # Exit without updating the correspondent

    if tag:
        logging.info(
            f"Document {doc_id} processed successfully. Correspondent: {correspondent['name']}, Tag: {tag['name']}."
        )
    else:
        logging.info(
            f"Document {doc_id} processed successfully. Correspondent: {correspondent['name']}, No tag added."
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: postprocess.py <document_id>")
        sys.exit(1)

    document_id = sys.argv[1]
    main(document_id)
