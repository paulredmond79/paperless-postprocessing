#!/usr/bin/env python3
import os
import sys
import logging
import requests
import openai
import json
import time
import random
import jsonschema
from utils.api_helpers import (
    fetch_document_details,
    update_document_metadata,
    ensure_custom_field_exists,
    fetch_custom_fields,
    to_snake_case,
    fetch_tags,
    create_tag,
    fetch_or_create_tag,
    update_document_metadata as update_document,  # Alias for backward compatibility
    add_tag_to_document,
)

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

client = openai.OpenAI(api_key=openai_api_key)

# Load prompts from external file
PROMPT_FILE = os.path.join(os.path.dirname(__file__), "tax_relief_prompts.json")
FIELD_MAPPING_FILE = os.path.join(os.path.dirname(__file__), "field_mapping.json")

try:
    with open(PROMPT_FILE, "r") as f:
        prompts = json.load(f)
        user_prompt = prompts.get("user_prompt", "")
        system_prompt = prompts.get("system_prompt", "")
except Exception as e:
    logging.error(f"Failed to load prompts: {e}")
    sys.exit(1)

try:
    with open(FIELD_MAPPING_FILE, "r") as f:
        field_mapping = json.load(f)
except Exception as e:
    logging.error(f"Failed to load field mapping: {e}")
    sys.exit(1)

def fetch_document_ocr(document_id):
    """
    Fetches the OCR data of a document by its ID using the helper function.
    """
    logging.info(f"Fetching OCR data for document ID {document_id}.")
    try:
        document_details = fetch_document_details(paperless_url, headers, document_id)
        return document_details.get("content", "").strip()
    except Exception as e:
        logging.error(f"Failed to fetch OCR data: {e}")
        return None

def analyze_document_with_openai(ocr_data, document_id):
    """
    Sends OCR data to OpenAI to determine if it qualifies for tax relief.
    Implements retry logic with exponential backoff for rate limit errors.
    Handles additional HTTP status codes like 428 and 429.
    Validates the API response against the tax relief schema.
    If validation fails, adds a "tax-check-failed" tag to the document and proceeds.
    """
    logging.info("Analyzing OCR data with OpenAI.")
    max_retries = 5
    backoff_factor = 2

    # Load the tax relief schema
    schema_path = os.path.join(os.path.dirname(__file__), "tax_relief_schema.json")
    try:
        with open(schema_path, "r") as schema_file:
            tax_relief_schema = json.load(schema_file)
    except Exception as e:
        logging.error(f"Failed to load tax relief schema: {e}")
        return None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt + ocr_data},
                ],
            )
            result = response.choices[0].message.content

            # Validate the response against the schema
            try:
                jsonschema.validate(instance=json.loads(result), schema=tax_relief_schema)
                return result
            except jsonschema.ValidationError as ve:
                logging.error(f"Validation error: {ve.message}")
                logging.info("Adding 'tax-check-failed' tag to the document.")

                # Use the fetch_or_create_tag function to ensure the tag exists
                tag_id = fetch_or_create_tag(paperless_url, headers, "tax-check-failed")
                add_tag_to_document(paperless_url, headers, document_id, tag_id)

                return None

        except openai.RateLimitError as e:
            retry_after = backoff_factor ** attempt + random.uniform(0, 1)
            if hasattr(e, 'headers') and 'Retry-After' in e.headers:
                retry_after = int(e.headers['Retry-After'])
            logging.warning(f"Rate limit exceeded (429 Too Many Requests). Retrying in {retry_after} seconds...")
            time.sleep(retry_after)
        except openai.OpenAIError as e:
            if e.http_status == 428:
                logging.error("Precondition Required (428). Ensure the request meets the required conditions.")
                break
            logging.error(f"OpenAI API error: {e}")
            break
    logging.error("Failed to analyze document with OpenAI after multiple attempts.")
    return None

def ensure_custom_fields(api_url, headers, fields):
    """
    Ensures all custom fields in the mapping exist in Paperless-ngx.
    If a custom field does not exist, it will be created.
    """
    for key, field in fields.items():
        try:
            if isinstance(field, str):
                # Handle simple string mappings
                logging.info(f"Ensuring custom field '{field}' exists.")
                ensure_custom_field_exists(api_url, headers, field, "string")
            elif isinstance(field, dict):
                # Handle detailed mappings with name and data_type
                logging.info(f"Ensuring custom field '{field['name']}' exists.")
                ensure_custom_field_exists(api_url, headers, field["name"], field["data_type"])
            else:
                logging.warning(f"Unexpected field mapping format for key '{key}': {field}")
        except Exception as e:
            logging.error(f"Failed to ensure custom field for key '{key}' with field '{field}': {e}")
            # Continue processing other fields instead of exiting
            continue

def populate_field_mapping_with_ids(api_url, headers, field_mapping):
    """
    Fetches custom field metadata and updates the field_mapping with their IDs.
    """
    try:
        custom_fields = fetch_custom_fields(api_url, headers)
        logging.debug(f"Fetched custom fields from API: {custom_fields}")

        # Normalize custom field names to snake case for matching
        normalized_custom_fields = {to_snake_case(name): data for name, data in custom_fields.items()}

        # Update field_mapping with IDs and names from the API
        for key, field in field_mapping.items():
            if isinstance(field, dict):
                field_name = to_snake_case(field.get("name"))
                if field_name in normalized_custom_fields:
                    field_mapping[key]["id"] = normalized_custom_fields[field_name]["id"]
                    field_mapping[key]["name"] = field_name  # Ensure name matches API
                    logging.debug(f"Updated field mapping for key '{key}': {field_mapping[key]}")
                else:
                    logging.warning(f"No matching custom field found for key '{key}' with name '{field_name}'")
            else:
                logging.warning(f"Field mapping for key '{key}' is not a dictionary: {field}")

        # Log keys missing IDs
        missing_ids = [key for key, field in field_mapping.items() if isinstance(field, dict) and "id" not in field]
        if missing_ids:
            logging.warning(f"The following keys are missing 'id' values: {missing_ids}")

        logging.debug(f"Final field mapping after update: {field_mapping}")
    except Exception as e:
        logging.error(f"Failed to populate field mapping with IDs: {e}")
        sys.exit(1)

def update_document_with_json(api_url, headers, doc_id, json_data):
    """
    Updates the document in Paperless-ngx with the custom fields and combined notes.
    """
    import requests

    # Preprocess json_data to convert nested JSON objects to prettified strings
    processed_json_data = {
        key: (
            json.dumps(value, indent=4) if isinstance(value, (dict, list)) else value
        )
        for key, value in json_data.items()
    }

    # Add all custom fields to the payload, excluding detected_services and analysis
    custom_fields = [
        {"field": field_mapping[key]["id"], "value": processed_json_data[key]}
        for key in processed_json_data
        if key in field_mapping and key not in ["detected_services", "analysis"]
    ]

    # Combine analysis and detected_services into a single notes field
    analysis = processed_json_data.get("analysis", "")
    detected_services = processed_json_data.get("detected_services", "")
    combined_notes = f"{analysis}\n\nDetected Services:\n{detected_services}" if analysis or detected_services else None

    # Update custom fields
    if custom_fields:
        update_data = {"custom_fields": custom_fields}
        update_document(api_url, headers, doc_id, update_data)

    # Update notes field
    if combined_notes:
        notes_url = f"{api_url}/api/documents/{doc_id}/notes/"
        notes_payload = {"note": combined_notes}
        response = requests.post(notes_url, headers=headers, json=notes_payload)
        response.raise_for_status()

def main():
    if len(sys.argv) != 2:
        logging.error("Usage: ocr_tax_relief_checker.py <document_id>")
        sys.exit(1)

    document_id = sys.argv[1]

    # Fetch OCR data
    ocr_data = fetch_document_ocr(document_id)
    if not ocr_data:
        logging.error("No OCR data found.")
        sys.exit(1)

    # Analyze with OpenAI
    result = analyze_document_with_openai(ocr_data, document_id)
    if not result:
        logging.error("Failed to analyze document with OpenAI.")
        sys.exit(1)

    # Parse JSON response
    try:
        json_data = json.loads(result)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse OpenAI response: {e}")
        sys.exit(1)

    # Populate field mapping with IDs
    populate_field_mapping_with_ids(paperless_url, headers, field_mapping)

    # Ensure custom fields exist
    ensure_custom_fields(paperless_url, headers, field_mapping)

    # Update document with JSON data
    update_document_with_json(paperless_url, headers, document_id, json_data)

    logging.info("Document updated successfully.")

if __name__ == "__main__":
    main()
