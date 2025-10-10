#!/usr/bin/env python3
"""
Unit tests for the ingest_document.py script.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add src directory to path for importing the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ingest_document import (  # noqa: E402
    create_http_session,
    get_rag_api_config,
    ingest_document,
    setup_logging,
)


class TestRagApiConfig(unittest.TestCase):
    """Test RAG API configuration functions."""

    @patch.dict(os.environ, {}, clear=True)
    def test_get_rag_api_config_defaults(self):
        """Test default configuration when no environment variables are set."""
        url, api_key = get_rag_api_config()
        self.assertEqual(url, "http://localhost:8000")
        self.assertIsNone(api_key)

    @patch.dict(
        os.environ, {"RAG_API_URL": "http://example.com/", "RAG_API_KEY": "test-key"}
    )
    def test_get_rag_api_config_with_env_vars(self):
        """Test configuration with environment variables set."""
        url, api_key = get_rag_api_config()
        self.assertEqual(url, "http://example.com")  # Should strip trailing slash
        self.assertEqual(api_key, "test-key")

    @patch.dict(os.environ, {"RAG_API_URL": "http://example.com/"})
    def test_get_rag_api_config_strips_trailing_slash(self):
        """Test that trailing slashes are stripped from URL."""
        url, _ = get_rag_api_config()
        self.assertEqual(url, "http://example.com")


class TestLogging(unittest.TestCase):
    """Test logging setup."""

    def test_setup_logging(self):
        """Test that logging is configured correctly."""
        logger = setup_logging()
        self.assertEqual(logger.name, "paperless_rag_ingest")
        self.assertTrue(logger.hasHandlers())


class TestHttpSession(unittest.TestCase):
    """Test HTTP session creation."""

    @patch("ingest_document.requests.Session")
    @patch("ingest_document.HTTPAdapter")
    @patch("ingest_document.Retry")
    def test_create_http_session(self, mock_retry, mock_adapter, mock_session):
        """Test HTTP session creation with retry configuration."""
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance

        session = create_http_session()

        # Verify session was created and configured
        mock_session.assert_called_once()
        mock_retry.assert_called_once()
        mock_adapter.assert_called_once()
        self.assertEqual(session, mock_session_instance)


class TestIngestDocument(unittest.TestCase):
    """Test the main ingest_document function."""

    @patch("ingest_document.get_rag_api_config")
    @patch("ingest_document.create_http_session")
    @patch("ingest_document.setup_logging")
    def test_ingest_document_success(
        self, mock_setup_logging, mock_create_session, mock_get_config
    ):
        """Test successful document ingestion."""
        # Setup mocks
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        mock_get_config.return_value = ("http://localhost:8000", "test-key")

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "processed_docs": 1,
            "new_chunks": 5,
            "updated_chunks": 0,
            "processing_time_ms": 1500,
            "errors": [],
        }
        mock_session.post.return_value = mock_response
        mock_create_session.return_value = mock_session

        # Test the function
        result = ingest_document("123")

        # Verify success
        self.assertTrue(result)
        mock_session.post.assert_called_once()

        # Verify the request was made correctly
        call_args = mock_session.post.call_args
        # First positional arg should be the URL
        self.assertEqual(call_args[0][0], "http://localhost:8000/ingest/by_id")
        # Check JSON payload and headers
        expected_json = {"doc_id": "123", "force_refresh": False}
        self.assertEqual(call_args[1]["json"], expected_json)
        self.assertEqual(call_args[1]["headers"]["X-API-Key"], "test-key")

    @patch("ingest_document.get_rag_api_config")
    @patch("ingest_document.create_http_session")
    @patch("ingest_document.setup_logging")
    def test_ingest_document_no_api_key(
        self, mock_setup_logging, mock_create_session, mock_get_config
    ):
        """Test ingestion without API key."""
        # Setup mocks
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        mock_get_config.return_value = ("http://localhost:8000", None)

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "processed_docs": 1,
            "new_chunks": 5,
            "updated_chunks": 0,
            "processing_time_ms": 1500,
            "errors": [],
        }
        mock_session.post.return_value = mock_response
        mock_create_session.return_value = mock_session

        # Test the function
        result = ingest_document("123")

        # Verify success
        self.assertTrue(result)

        # Verify no API key was included
        call_args = mock_session.post.call_args
        self.assertNotIn("X-API-Key", call_args[1]["headers"])

    @patch("ingest_document.get_rag_api_config")
    @patch("ingest_document.create_http_session")
    @patch("ingest_document.setup_logging")
    def test_ingest_document_http_error(
        self, mock_setup_logging, mock_create_session, mock_get_config
    ):
        """Test handling of HTTP errors."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        mock_get_config.return_value = ("http://localhost:8000", None)

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_session.post.return_value = mock_response
        mock_create_session.return_value = mock_session

        # Test the function
        result = ingest_document("123")

        # Verify failure
        self.assertFalse(result)

    @patch("ingest_document.get_rag_api_config")
    @patch("ingest_document.create_http_session")
    @patch("ingest_document.setup_logging")
    def test_ingest_document_validation_error(
        self, mock_setup_logging, mock_create_session, mock_get_config
    ):
        """Test handling of validation errors."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        mock_get_config.return_value = ("http://localhost:8000", None)

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {"detail": "Invalid document ID"}
        mock_session.post.return_value = mock_response
        mock_create_session.return_value = mock_session

        # Test the function
        result = ingest_document("123")

        # Verify failure
        self.assertFalse(result)

    @patch("ingest_document.get_rag_api_config")
    @patch("ingest_document.create_http_session")
    @patch("ingest_document.setup_logging")
    def test_ingest_document_connection_error(
        self, mock_setup_logging, mock_create_session, mock_get_config
    ):
        """Test handling of connection errors."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        mock_get_config.return_value = ("http://localhost:8000", None)

        mock_session = Mock()
        mock_session.post.side_effect = Exception("Connection refused")
        mock_create_session.return_value = mock_session

        # Test the function
        with self.assertLogs("paperless_rag_ingest", level="INFO"):
            ingest_document("123")

    @patch("ingest_document.get_rag_api_config")
    @patch("ingest_document.create_http_session")
    @patch("ingest_document.setup_logging")
    def test_ingest_document_timeout_error(
        self, mock_setup_logging, mock_create_session, mock_get_config
    ):
        """Test handling of timeout errors."""
        import requests

        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        mock_get_config.return_value = ("http://localhost:8000", None)

        mock_session = Mock()
        mock_session.post.side_effect = requests.exceptions.Timeout()
        mock_create_session.return_value = mock_session

        # Test the function
        result = ingest_document("123")

        # Verify failure
        self.assertFalse(result)

    @patch("ingest_document.get_rag_api_config")
    @patch("ingest_document.create_http_session")
    @patch("ingest_document.setup_logging")
    def test_ingest_document_json_decode_error(
        self, mock_setup_logging, mock_create_session, mock_get_config
    ):
        """Test handling of JSON decode errors."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        mock_get_config.return_value = ("http://localhost:8000", None)

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_session.post.return_value = mock_response
        mock_create_session.return_value = mock_session

        # Test the function
        result = ingest_document("123")

        # Verify failure
        self.assertFalse(result)


class TestMainFunction(unittest.TestCase):
    """Test the main function and CLI interface."""

    @patch("ingest_document.ingest_document")
    @patch("ingest_document.setup_logging")
    @patch("sys.argv", ["ingest_document.py", "123"])
    def test_main_success(self, mock_setup_logging, mock_ingest):
        """Test successful main function execution."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_ingest.return_value = True

        with self.assertRaises(SystemExit) as cm:
            import ingest_document

            ingest_document.main()

        # Should exit with code 0 for success
        self.assertEqual(cm.exception.code, 0)
        mock_ingest.assert_called_once_with("123", False)

    @patch("ingest_document.ingest_document")
    @patch("ingest_document.setup_logging")
    @patch("sys.argv", ["ingest_document.py", "123", "--force-refresh"])
    def test_main_with_force_refresh(self, mock_setup_logging, mock_ingest):
        """Test main function with force refresh flag."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_ingest.return_value = True

        with self.assertRaises(SystemExit) as cm:
            import ingest_document

            ingest_document.main()

        # Should exit with code 0 for success
        self.assertEqual(cm.exception.code, 0)
        mock_ingest.assert_called_once_with("123", True)

    @patch("ingest_document.ingest_document")
    @patch("ingest_document.setup_logging")
    @patch("sys.argv", ["ingest_document.py", "123", "--verbose"])
    def test_main_with_verbose(self, mock_setup_logging, mock_ingest):
        """Test main function with verbose flag."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_ingest.return_value = True

        with self.assertRaises(SystemExit) as cm:
            import ingest_document

            ingest_document.main()

        # Should exit with code 0 for success
        self.assertEqual(cm.exception.code, 0)

    @patch("ingest_document.ingest_document")
    @patch("ingest_document.setup_logging")
    @patch("sys.argv", ["ingest_document.py", "123"])
    def test_main_ingestion_failure(self, mock_setup_logging, mock_ingest):
        """Test main function when ingestion fails."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_ingest.return_value = False

        with self.assertRaises(SystemExit) as cm:
            import ingest_document

            ingest_document.main()

        # Should exit with code 1 for failure
        self.assertEqual(cm.exception.code, 1)

    @patch("ingest_document.setup_logging")
    @patch("sys.argv", ["ingest_document.py", "invalid_id"])
    def test_main_invalid_document_id(self, mock_setup_logging):
        """Test main function with invalid document ID."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        with self.assertRaises(SystemExit) as cm:
            import ingest_document

            ingest_document.main()

        # Should exit with code 1 for invalid input
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
