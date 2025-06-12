#!/usr/bin/env python3
import json
import logging
import os
import re
import sys
from datetime import datetime

from openai import OpenAI

from utils.api_helpers import (
    fetch_document_details,
    update_document_metadata,
    ensure_custom_field_exists,
    fetch_custom_fields,
    to_snake_case,
    fetch_tags,
    create_tag,
    fetch_or_create_tag,  # Removed alias ensure_tag_exists
)

logging.basicConfig(level=logging.INFO)


def clean_fields(fields, field_meta):
    """Cleans and normalizes field values based on their metadata."""
    cleaned = {}

    for key, value in fields.items():
        value = str(value).strip() if not isinstance(value, str) else value.strip()
        meta = field_meta.get(key)

        if not meta:
            logging.warning(f"Skipping cleaning for unknown field: {key}")
            continue

        data_type = meta["data_type"]

        try:
            if data_type == "date":
                # Try multiple date formats
                for date_format in ["%d.%m.%Y", "%d/%m/%Y", "%d %b %y"]:
                    try:
                        value = datetime.strptime(value, date_format).strftime(
                            "%Y-%m-%d"
                        )
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"Unsupported date format for '{key}': {value}")
            elif data_type == "monetary":
                value = re.sub(r"[^\d,.-]", "", value).replace(",", ".")
                value = str(round(float(value.replace(",", "").replace(" ", "")), 2))
        except ValueError:
            logging.warning(f"Invalid format for '{key}': {value}, skipping.")
            continue

        cleaned[key] = value

    return cleaned


def generate_metadata_with_openai(content, field_keys):
    """Generates metadata using OpenAI based on OCR content."""
    prompt = f"""
    You are a document assistant. Based on the OCR text below, perform the following tasks:

    1. Generate a concise and descriptive title for the document.
    2. Extract the following metadata fields using the exact snake_case keys listed:

    {', '.join(field_keys)}

    Return a JSON object with the following structure:
    {{
      "title": "<generated_title>",
      "fields": {{
        <field_key>: <field_value>,
        ...
      }}
    }}

    If a field is not present in the text, do not include it in the "fields" object.

    Text:
    {content}
    """

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        ai_response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You're a document assistant for metadata extraction and title generation.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        raw_output = ai_response.choices[0].message.content
        logging.info(f"Raw OpenAI output: {raw_output[:300]}")

        json_text_match = re.search(r"\{.*\}", raw_output, re.DOTALL)
        if not json_text_match:
            raise ValueError("Could not find valid JSON in OpenAI output.")
        return json.loads(json_text_match.group(0))
    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        sys.exit(1)


def main(doc_id):
    """Main function to process a document by its ID."""
    logging.info(f"Starting metadata extraction for document ID: {doc_id}")

    api_url = os.getenv("PAPERLESS_URL", "http://localhost:8000")
    headers = {
        "Authorization": f"Token {os.getenv('PAPERLESS_API_TOKEN')}",
        "Content-Type": "application/json",
    }

    document_details = fetch_document_details(api_url, headers, doc_id)
    content = document_details.get("content", "")
    if not content:
        logging.warning("No OCR content found for document.")
        sys.exit(0)

    field_map = fetch_custom_fields(api_url, headers)
    field_keys = list(field_map.keys())
    if not field_keys:
        logging.warning("No custom fields found.")
        sys.exit(0)

    metadata = generate_metadata_with_openai(content, field_keys)
    generated_title = metadata.get("title", "").strip()
    extracted_fields = metadata.get("fields", {})

    cleaned_fields = clean_fields(extracted_fields, field_map)

    custom_fields_payload = [
        {"field": field_map[key]["id"], "value": value}
        for key, value in cleaned_fields.items()
        if key in field_map
    ]

    payload = {"title": generated_title, "custom_fields": custom_fields_payload}

    update_document_metadata(api_url, headers, doc_id, payload)
    logging.info(
        f"Successfully updated document {doc_id} with title and custom fields."
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: post.py <document_id>")
        sys.exit(1)

    document_id = sys.argv[1]
    main(document_id)
