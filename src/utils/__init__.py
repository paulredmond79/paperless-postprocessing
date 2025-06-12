from .api_helpers import (
    create_correspondent,
    get_correspondents,
    fetch_tags,
    create_tag,
    fetch_or_create_tag,  # Removed alias ensure_tag_exists
    add_tag_to_document,
    fetch_document_details,
    update_document_metadata,
    fetch_custom_fields,
    ensure_custom_field_exists,
    to_snake_case,
)

__all__ = [
    "create_correspondent",
    "get_correspondents",
    "fetch_tags",
    "create_tag",
    "fetch_or_create_tag",  # Removed alias ensure_tag_exists
    "add_tag_to_document",
    "fetch_document_details",
    "update_document_metadata",
    "fetch_custom_fields",
    "ensure_custom_field_exists",
    "to_snake_case",
]
