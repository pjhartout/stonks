"""Tests for stonks logging configuration."""

import os
from unittest.mock import patch

import stonks.logging_config as logging_config
from stonks.logging_config import _resolve_stdout_level


class TestResolveStdoutLevel:
    def test_default_is_warning(self):
        """Without env var, default stdout level is WARNING."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("STONKS_LOG_LEVEL", None)
            assert _resolve_stdout_level() == "WARNING"

    def test_debug_level(self):
        """STONKS_LOG_LEVEL=DEBUG returns DEBUG."""
        with patch.dict(os.environ, {"STONKS_LOG_LEVEL": "DEBUG"}):
            assert _resolve_stdout_level() == "DEBUG"

    def test_warning_level(self):
        """STONKS_LOG_LEVEL=WARNING returns WARNING."""
        with patch.dict(os.environ, {"STONKS_LOG_LEVEL": "WARNING"}):
            assert _resolve_stdout_level() == "WARNING"

    def test_error_level(self):
        """STONKS_LOG_LEVEL=ERROR returns ERROR."""
        with patch.dict(os.environ, {"STONKS_LOG_LEVEL": "ERROR"}):
            assert _resolve_stdout_level() == "ERROR"

    def test_case_insensitive(self):
        """Log level is case-insensitive."""
        with patch.dict(os.environ, {"STONKS_LOG_LEVEL": "debug"}):
            assert _resolve_stdout_level() == "DEBUG"

    def test_level_with_whitespace(self):
        """Log level with surrounding whitespace is trimmed."""
        with patch.dict(os.environ, {"STONKS_LOG_LEVEL": "  INFO  "}):
            assert _resolve_stdout_level() == "INFO"

    def test_invalid_level_falls_back_to_warning(self):
        """Invalid log level falls back to WARNING."""
        with patch.dict(os.environ, {"STONKS_LOG_LEVEL": "TRACE"}):
            assert _resolve_stdout_level() == "WARNING"

    def test_empty_string_falls_back_to_warning(self):
        """Empty string falls back to WARNING."""
        with patch.dict(os.environ, {"STONKS_LOG_LEVEL": ""}):
            assert _resolve_stdout_level() == "WARNING"


class TestSetupLogging:
    def test_setup_creates_log_directory(self, tmp_path):
        """setup_logging creates the log directory."""
        log_dir = str(tmp_path / "test_logs")
        # Reset the global flag
        old_configured = logging_config._configured
        logging_config._configured = False
        try:
            logging_config.setup_logging(log_dir=log_dir)
            assert (tmp_path / "test_logs").is_dir()
        finally:
            logging_config._configured = old_configured

    def test_setup_is_idempotent(self, tmp_path):
        """setup_logging only configures once."""
        log_dir = str(tmp_path / "test_logs")
        old_configured = logging_config._configured
        logging_config._configured = False
        try:
            logging_config.setup_logging(log_dir=log_dir)
            assert logging_config._configured is True
            # Second call should be a no-op
            logging_config.setup_logging(log_dir=str(tmp_path / "other_logs"))
            assert not (tmp_path / "other_logs").exists()
        finally:
            logging_config._configured = old_configured
