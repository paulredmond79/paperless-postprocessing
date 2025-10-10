#!/usr/bin/env python3
"""
Paperless-NGX post-processing script to ingest documents into RAG system.

This script is designed to be called by Paperless-NGX post-processing hooks
to automatically ingest documents into the RAG system after they are processed.
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Optional

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError as e:
    print(f"Error: Required dependencies not installed: {e}")
    print("Please install required packages: pip install requests")
    sys.exit(1)


def setup_logging() -> logging.Logger:
    """Set up logging configuration for Paperless-NGX visibility."""
    logger = logging.getLogger("paperless_rag_ingest")
    logger.setLevel(logging.INFO)

    # Create handler that outputs to stdout for Paperless-NGX to capture
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)

    # Format messages for clear identification in Paperless-NGX logs
    formatter = logging.Formatter(
        "[RAG-INGEST] %(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


def get_rag_api_config() -> tuple[str, Optional[str]]:
    """Get RAG API configuration from environment variables."""
    rag_url = os.getenv("RAG_API_URL", "http://localhost:8000")
    rag_api_key = os.getenv("RAG_API_KEY")

    # Ensure URL doesn't end with slash
    rag_url = rag_url.rstrip("/")

    return rag_url, rag_api_key


def create_http_session() -> requests.Session:
    """Create HTTP session with retry strategy."""
    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def ingest_document(doc_id: str, force_refresh: bool = False) -> bool:
    """
    Ingest a document into the RAG system.

    Args:
        doc_id: Document ID to ingest
        force_refresh: Whether to force re-ingestion if document exists

    Returns:
        True if successful, False otherwise
    """
    logger = logging.getLogger("paperless_rag_ingest")
    rag_url = ""  # Initialize to prevent unbound variable issues

    try:
        # Get configuration
        rag_url, rag_api_key = get_rag_api_config()

        logger.info(f"Starting ingestion for document ID: {doc_id}")
        logger.info(f"RAG API URL: {rag_url}")
        logger.info(f"Force refresh: {force_refresh}")

        # Prepare request
        url = f"{rag_url}/ingest/by_id"
        headers = {"Content-Type": "application/json"}

        if rag_api_key:
            headers["X-API-Key"] = rag_api_key
            logger.info("Using API key authentication")
        else:
            logger.warning("No RAG_API_KEY found - proceeding without authentication")

        payload = {"doc_id": doc_id, "force_refresh": force_refresh}

        # Make request
        session = create_http_session()
        start_time = time.time()

        logger.info(f"Sending request to {url}")
        response = session.post(
            url, json=payload, headers=headers, timeout=300  # 5 minute timeout
        )

        elapsed_time = time.time() - start_time

        # Handle response
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Ingestion successful (took {elapsed_time:.2f}s)")
            logger.info(f"   Processed docs: {result.get('processed_docs', 0)}")
            logger.info(f"   New chunks: {result.get('new_chunks', 0)}")
            logger.info(f"   Updated chunks: {result.get('updated_chunks', 0)}")
            logger.info(f"   Processing time: {result.get('processing_time_ms', 0)}ms")

            if result.get("errors"):
                logger.warning(f"   Errors encountered: {result['errors']}")

            return True

        elif response.status_code == 422:
            error_detail = response.json().get("detail", "Unknown validation error")
            logger.error(f"❌ Validation error: {error_detail}")
            return False

        else:
            logger.error(f"❌ HTTP {response.status_code}: {response.text}")
            return False

    except requests.exceptions.Timeout:
        logger.error("❌ Request timed out after 5 minutes")
        return False

    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Could not connect to RAG API at {rag_url}")
        logger.error(
            "   Check that the RAG service is running and RAG_API_URL is correct"
        )
        return False

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Request failed: {e}")
        return False

    except json.JSONDecodeError:
        logger.error("❌ Invalid JSON response from RAG API")
        return False

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Ingest a Paperless-NGX document into the RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  RAG_API_URL      RAG API base URL (default: http://localhost:8000)
  RAG_API_KEY      RAG API authentication key (optional)

Examples:
  %(prog)s 123
  %(prog)s 456 --force-refresh
        """,
    )

    parser.add_argument("document_id", help="Paperless-NGX document ID to ingest")

    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force re-ingestion if document already exists in RAG system",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set up logging
    logger = setup_logging()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    # Validate document ID
    try:
        # Ensure it's a valid integer (Paperless-NGX uses integer IDs)
        int(args.document_id)
    except ValueError:
        logger.error(
            f"❌ Invalid document ID: '{args.document_id}' (must be an integer)"
        )
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Paperless-NGX RAG Document Ingestion")
    logger.info("=" * 60)

    # Perform ingestion
    success = ingest_document(args.document_id, args.force_refresh)

    if success:
        logger.info("=" * 60)
        logger.info("✅ Document ingestion completed successfully")
        sys.exit(0)
    else:
        logger.error("=" * 60)
        logger.error("❌ Document ingestion failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
