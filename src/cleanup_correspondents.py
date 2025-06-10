#!/usr/bin/env python3
import json
import logging
import os

import requests

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


def fetch_all_correspondents():
    """
    Fetches all correspondents from Paperless-ngx.
    """
    logging.info("Fetching all correspondents from Paperless-ngx.")
    correspondents = []
    next_url = f"{paperless_url}/api/correspondents/?page_size=100"

    while next_url:
        response = requests.get(next_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        correspondents.extend(data.get("results", []))
        next_url = data.get("next")

    logging.info(f"Fetched {len(correspondents)} correspondents.")
    return correspondents


def update_correspondent(correspondent_id, new_name):
    """
    Updates the name of a correspondent.
    """
    logging.info(
        f"Updating correspondent ID {correspondent_id} with new name: {new_name}."
    )
    url = f"{paperless_url}/api/correspondents/{correspondent_id}/"
    payload = {"name": new_name}
    response = requests.patch(url, headers=headers, json=payload)
    response.raise_for_status()
    logging.info(f"Correspondent ID {correspondent_id} updated successfully.")


def main():
    logging.info("Starting correspondent JSON name cleanup.")

    # Fetch all correspondents
    correspondents = fetch_all_correspondents()

    for correspondent in correspondents:
        correspondent_id = correspondent["id"]
        correspondent_name = correspondent["name"]

        # Check if the name is a JSON string
        try:
            name_data = json.loads(correspondent_name)
            if isinstance(name_data, dict) and "correspondent" in name_data:
                new_name = name_data["correspondent"]
                logging.info(
                    f"Found JSON name for correspondent ID {correspondent_id}. Extracted name: {new_name}."
                )

                # Update the correspondent with the extracted name
                update_correspondent(correspondent_id, new_name)
        except json.JSONDecodeError:
            # Name is not JSON, skip
            logging.debug(
                f"Correspondent ID {correspondent_id} has a plain text name. Skipping."
            )

    logging.info("Correspondent JSON name cleanup completed.")


if __name__ == "__main__":
    main()
