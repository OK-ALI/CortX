"""CortX logging module — color-coded console + rotating file log."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ANSI color codes for terminal
class _Colors:
    RESET = "\033[0m"
    GREY = "\033[90m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"


class ColorFormatter(logging.Formatter):
    """Formatter that adds color to console log output."""

    LEVEL_COLORS = {
        logging.DEBUG: _Colors.GREY,
        logging.INFO: _Colors.CYAN,
        logging.WARNING: _Colors.YELLOW,
        logging.ERROR: _Colors.RED,
        logging.CRITICAL: _Colors.RED + _Colors.BOLD,
    }

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s │ %(levelname)-7s │ %(message)s",
            datefmt="%H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, _Colors.RESET)
        record.levelname = f"{color}{record.levelname}{_Colors.RESET}"

        # Color the separator and timestamp
        formatted = super().format(record)
        formatted = formatted.replace("│", f"{_Colors.GREY}│{_Colors.RESET}")
        return formatted


class FileFormatter(logging.Formatter):
    """Clean formatter for the log file (no ANSI codes)."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def setup_logger(log_level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    """Create the application logger with colored console + rotating file handlers."""
    logger = logging.getLogger("cortx")
    if logger.handlers:
        return logger

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Console handler — colored output
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(ColorFormatter())
    logger.addHandler(console)

    # File handler — plain text, rotating
    file_handler = RotatingFileHandler(
        Path(log_dir) / "cortx.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(FileFormatter())
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
