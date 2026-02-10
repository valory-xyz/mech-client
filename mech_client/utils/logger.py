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

"""Structured logging configuration for mech client."""

import logging
import sys
from typing import Optional


# ANSI color codes for terminal output
class Colors:  # pylint: disable=too-few-public-methods
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Text colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""

    # Log level to color mapping
    LEVEL_COLORS = {
        logging.DEBUG: Colors.DIM + Colors.WHITE,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BOLD + Colors.RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.

        :param record: Log record to format
        :return: Formatted log string with colors
        """
        # Add color to level name
        levelname = record.levelname
        if record.levelno in self.LEVEL_COLORS:
            levelname_color = (
                self.LEVEL_COLORS[record.levelno] + levelname + Colors.RESET
            )
            record.levelname = levelname_color

        # Format the message
        result = super().format(record)

        # Reset levelname to original (avoid side effects)
        record.levelname = levelname

        return result


def setup_logger(
    name: str = "mech_client",
    level: int = logging.INFO,
    use_colors: bool = True,
) -> logging.Logger:
    """
    Setup structured logger for mech client.

    Creates a logger with consistent formatting, optional colors, and
    appropriate handlers for CLI output.

    :param name: Logger name
    :param level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    :param use_colors: Whether to use colored output for terminal
    :return: Configured logger instance
    """
    log = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if log.handlers:
        return log

    log.setLevel(level)
    log.propagate = False

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Create formatter
    formatter: logging.Formatter
    if use_colors and sys.stdout.isatty():
        # Use colored formatter for terminal output
        formatter = ColoredFormatter(
            fmt="%(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # Plain formatter for non-terminal or when colors disabled
        formatter = logging.Formatter(
            fmt="%(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)

    return log


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get logger instance.

    Returns the root mech_client logger or a child logger if name is
    provided.

    :param name: Optional logger name for child logger
    :return: Logger instance
    """
    if name:
        return logging.getLogger(f"mech_client.{name}")
    return logging.getLogger("mech_client")


def set_log_level(level: int) -> None:
    """
    Set logging level for mech client logger.

    :param level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log = logging.getLogger("mech_client")
    log.setLevel(level)
    for handler in log.handlers:
        handler.setLevel(level)


# Default logger instance
logger = setup_logger()


# Convenience functions for common log operations
def debug(msg: str, *args, **kwargs) -> None:  # type: ignore
    """
    Log debug message.

    :param msg: Message to log
    :param args: Positional arguments for message formatting
    :param kwargs: Keyword arguments for logger
    """
    logger.debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs) -> None:  # type: ignore
    """
    Log info message.

    :param msg: Message to log
    :param args: Positional arguments for message formatting
    :param kwargs: Keyword arguments for logger
    """
    logger.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs) -> None:  # type: ignore
    """
    Log warning message.

    :param msg: Message to log
    :param args: Positional arguments for message formatting
    :param kwargs: Keyword arguments for logger
    """
    logger.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs) -> None:  # type: ignore
    """
    Log error message.

    :param msg: Message to log
    :param args: Positional arguments for message formatting
    :param kwargs: Keyword arguments for logger
    """
    logger.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs) -> None:  # type: ignore
    """
    Log critical message.

    :param msg: Message to log
    :param args: Positional arguments for message formatting
    :param kwargs: Keyword arguments for logger
    """
    logger.critical(msg, *args, **kwargs)


def log_transaction(tx_hash: str, operation: str) -> None:
    """
    Log transaction with consistent format.

    :param tx_hash: Transaction hash
    :param operation: Operation being performed
    """
    info(f"✓ {operation} - TX: {tx_hash}")


def log_request(request_id: str, mech_address: str) -> None:
    """
    Log mech request with consistent format.

    :param request_id: Request ID
    :param mech_address: Mech address
    """
    info(f"✓ Request submitted - ID: {request_id}, Mech: {mech_address}")


def log_delivery(request_id: str, ipfs_hash: str) -> None:
    """
    Log delivery with consistent format.

    :param request_id: Request ID
    :param ipfs_hash: IPFS hash of delivered data
    """
    info(f"✓ Delivery received - ID: {request_id}, IPFS: {ipfs_hash[:16]}...")
