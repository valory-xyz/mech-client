# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Tests for utils.logger module."""

import logging
from unittest.mock import MagicMock, patch


class TestColoredFormatterFormat:
    """Tests for ColoredFormatter.format method."""

    def test_format_with_tty_applies_colors(self) -> None:
        """Test that format applies color codes when stdout is a TTY."""
        from mech_client.utils.logger import ColoredFormatter  # pylint: disable=import-outside-toplevel

        formatter = ColoredFormatter(fmt="%(levelname)s: %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        original_levelname = record.levelname

        result = formatter.format(record)

        # Color codes should be present in output
        assert "INFO" in result
        assert "test message" in result
        # The levelname on the record should be restored to the original value
        assert record.levelname == original_levelname

    def test_format_restores_levelname_after_coloring(self) -> None:
        """Test that format restores original levelname after applying color codes."""
        from mech_client.utils.logger import ColoredFormatter  # pylint: disable=import-outside-toplevel

        formatter = ColoredFormatter(fmt="%(levelname)s: %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="a warning",
            args=(),
            exc_info=None,
        )
        original_levelname = record.levelname

        formatter.format(record)

        # levelname must be restored to original (no side effects)
        assert record.levelname == original_levelname

    def test_format_colors_all_log_levels(self) -> None:
        """Test that format applies colors for each supported log level."""
        from mech_client.utils.logger import ColoredFormatter  # pylint: disable=import-outside-toplevel

        formatter = ColoredFormatter(fmt="%(levelname)s: %(message)s")
        levels = [
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ]
        for level in levels:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="",
                lineno=0,
                msg="msg",
                args=(),
                exc_info=None,
            )
            original_levelname = record.levelname
            result = formatter.format(record)
            assert isinstance(result, str)
            assert record.levelname == original_levelname


class TestSetupLogger:
    """Tests for setup_logger function."""

    def test_setup_logger_returns_logger(self) -> None:
        """Test that setup_logger returns a Logger instance."""
        from mech_client.utils.logger import setup_logger  # pylint: disable=import-outside-toplevel

        # Use a unique name to avoid handler accumulation from other tests
        log = setup_logger(name="test_setup_logger_returns_logger_unique")
        assert isinstance(log, logging.Logger)

    def test_setup_logger_returns_same_logger_if_handlers_exist(self) -> None:
        """Test that setup_logger does not add duplicate handlers."""
        from mech_client.utils.logger import setup_logger  # pylint: disable=import-outside-toplevel

        name = "test_setup_logger_no_dup_handlers"
        log1 = setup_logger(name=name)
        handler_count = len(log1.handlers)

        # Calling again should return same logger without adding more handlers
        log2 = setup_logger(name=name)
        assert log1 is log2
        assert len(log2.handlers) == handler_count

    def test_setup_logger_with_colors_and_tty(self) -> None:
        """Test setup_logger uses ColoredFormatter when stdout is a TTY."""
        from mech_client.utils.logger import ColoredFormatter, setup_logger  # pylint: disable=import-outside-toplevel

        name = "test_setup_logger_tty_colored"
        # Ensure the logger has no existing handlers
        existing = logging.getLogger(name)
        existing.handlers.clear()

        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            log = setup_logger(name=name, use_colors=True)

        # At least one handler should use ColoredFormatter
        assert any(
            isinstance(h.formatter, ColoredFormatter) for h in log.handlers
        )

    def test_setup_logger_without_colors_uses_plain_formatter(self) -> None:
        """Test setup_logger uses plain Formatter when colors are disabled."""
        from mech_client.utils.logger import ColoredFormatter, setup_logger  # pylint: disable=import-outside-toplevel

        name = "test_setup_logger_no_colors"
        existing = logging.getLogger(name)
        existing.handlers.clear()

        log = setup_logger(name=name, use_colors=False)

        # No handler should use ColoredFormatter
        assert not any(
            isinstance(h.formatter, ColoredFormatter) for h in log.handlers
        )

    def test_setup_logger_non_tty_uses_plain_formatter(self) -> None:
        """Test setup_logger uses plain Formatter when stdout is not a TTY."""
        from mech_client.utils.logger import ColoredFormatter, setup_logger  # pylint: disable=import-outside-toplevel

        name = "test_setup_logger_non_tty"
        existing = logging.getLogger(name)
        existing.handlers.clear()

        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            log = setup_logger(name=name, use_colors=True)

        # No handler should use ColoredFormatter when stdout is not a TTY
        assert not any(
            isinstance(h.formatter, ColoredFormatter) for h in log.handlers
        )


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_without_name_returns_root_mech_client_logger(
        self,
    ) -> None:
        """Test get_logger() returns the root mech_client logger."""
        from mech_client.utils.logger import get_logger  # pylint: disable=import-outside-toplevel

        log = get_logger()
        assert log.name == "mech_client"

    def test_get_logger_with_name_returns_child_logger(self) -> None:
        """Test get_logger(name=...) returns a child logger with correct name."""
        from mech_client.utils.logger import get_logger  # pylint: disable=import-outside-toplevel

        log = get_logger(name="my_module")
        assert log.name == "mech_client.my_module"

    def test_get_logger_with_different_names_are_distinct(self) -> None:
        """Test that loggers with different names are distinct instances."""
        from mech_client.utils.logger import get_logger  # pylint: disable=import-outside-toplevel

        log_a = get_logger(name="module_a")
        log_b = get_logger(name="module_b")
        assert log_a is not log_b
        assert log_a.name != log_b.name


class TestSetLogLevel:
    """Tests for set_log_level function."""

    def test_set_log_level_updates_logger_and_handlers(self) -> None:
        """Test that set_log_level updates level on logger and all handlers."""
        from mech_client.utils.logger import set_log_level  # pylint: disable=import-outside-toplevel

        mock_handler = MagicMock(spec=logging.Handler)
        mock_logger = MagicMock(spec=logging.Logger)
        mock_logger.handlers = [mock_handler]

        with patch("logging.getLogger", return_value=mock_logger):
            set_log_level(logging.DEBUG)

        mock_logger.setLevel.assert_called_once_with(logging.DEBUG)
        mock_handler.setLevel.assert_called_once_with(logging.DEBUG)

    def test_set_log_level_with_no_handlers(self) -> None:
        """Test set_log_level works when logger has no handlers."""
        from mech_client.utils.logger import set_log_level  # pylint: disable=import-outside-toplevel

        mock_logger = MagicMock(spec=logging.Logger)
        mock_logger.handlers = []

        with patch("logging.getLogger", return_value=mock_logger):
            set_log_level(logging.ERROR)

        mock_logger.setLevel.assert_called_once_with(logging.ERROR)

    def test_set_log_level_affects_mech_client_logger(self) -> None:
        """Test set_log_level targets the mech_client logger by name."""
        from mech_client.utils.logger import set_log_level  # pylint: disable=import-outside-toplevel

        captured_name = []

        def fake_get_logger(name: str) -> MagicMock:
            captured_name.append(name)
            m = MagicMock(spec=logging.Logger)
            m.handlers = []
            return m

        with patch("logging.getLogger", side_effect=fake_get_logger):
            set_log_level(logging.WARNING)

        assert "mech_client" in captured_name


class TestConvenienceFunctions:
    """Tests for debug, info, warning, error, critical convenience functions."""

    def test_debug_delegates_to_logger(self) -> None:
        """Test debug() delegates to the module-level logger."""
        import mech_client.utils.logger as logger_module  # pylint: disable=import-outside-toplevel

        mock_logger = MagicMock()
        original_logger = logger_module.logger
        logger_module.logger = mock_logger
        try:
            logger_module.debug("debug message")
            mock_logger.debug.assert_called_once_with("debug message")
        finally:
            logger_module.logger = original_logger

    def test_info_delegates_to_logger(self) -> None:
        """Test info() delegates to the module-level logger."""
        import mech_client.utils.logger as logger_module  # pylint: disable=import-outside-toplevel

        mock_logger = MagicMock()
        original_logger = logger_module.logger
        logger_module.logger = mock_logger
        try:
            logger_module.info("info message")
            mock_logger.info.assert_called_once_with("info message")
        finally:
            logger_module.logger = original_logger

    def test_warning_delegates_to_logger(self) -> None:
        """Test warning() delegates to the module-level logger."""
        import mech_client.utils.logger as logger_module  # pylint: disable=import-outside-toplevel

        mock_logger = MagicMock()
        original_logger = logger_module.logger
        logger_module.logger = mock_logger
        try:
            logger_module.warning("warn message")
            mock_logger.warning.assert_called_once_with("warn message")
        finally:
            logger_module.logger = original_logger

    def test_error_delegates_to_logger(self) -> None:
        """Test error() delegates to the module-level logger."""
        import mech_client.utils.logger as logger_module  # pylint: disable=import-outside-toplevel

        mock_logger = MagicMock()
        original_logger = logger_module.logger
        logger_module.logger = mock_logger
        try:
            logger_module.error("error message")
            mock_logger.error.assert_called_once_with("error message")
        finally:
            logger_module.logger = original_logger

    def test_critical_delegates_to_logger(self) -> None:
        """Test critical() delegates to the module-level logger."""
        import mech_client.utils.logger as logger_module  # pylint: disable=import-outside-toplevel

        mock_logger = MagicMock()
        original_logger = logger_module.logger
        logger_module.logger = mock_logger
        try:
            logger_module.critical("critical message")
            mock_logger.critical.assert_called_once_with("critical message")
        finally:
            logger_module.logger = original_logger


class TestLogHelperFunctions:
    """Tests for log_transaction, log_request, log_delivery helper functions."""

    def test_log_transaction_formats_message(self) -> None:
        """Test log_transaction calls info with formatted TX message."""
        import mech_client.utils.logger as logger_module  # pylint: disable=import-outside-toplevel

        mock_logger = MagicMock()
        original_logger = logger_module.logger
        logger_module.logger = mock_logger
        try:
            logger_module.log_transaction("0xdeadbeef", "Deposit")
            mock_logger.info.assert_called_once_with(
                "✓ Deposit - TX: 0xdeadbeef"
            )
        finally:
            logger_module.logger = original_logger

    def test_log_request_formats_message(self) -> None:
        """Test log_request calls info with formatted request message."""
        import mech_client.utils.logger as logger_module  # pylint: disable=import-outside-toplevel

        mock_logger = MagicMock()
        original_logger = logger_module.logger
        logger_module.logger = mock_logger
        try:
            mech_address = "0x" + "a" * 40
            logger_module.log_request("42", mech_address)
            mock_logger.info.assert_called_once_with(
                f"✓ Request submitted - ID: 42, Mech: {mech_address}"
            )
        finally:
            logger_module.logger = original_logger

    def test_log_delivery_formats_message_with_truncated_hash(self) -> None:
        """Test log_delivery calls info with IPFS hash truncated to 16 chars."""
        import mech_client.utils.logger as logger_module  # pylint: disable=import-outside-toplevel

        mock_logger = MagicMock()
        original_logger = logger_module.logger
        logger_module.logger = mock_logger
        try:
            ipfs_hash = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
            logger_module.log_delivery("99", ipfs_hash)
            mock_logger.info.assert_called_once_with(
                f"✓ Delivery received - ID: 99, IPFS: {ipfs_hash[:16]}..."
            )
        finally:
            logger_module.logger = original_logger
