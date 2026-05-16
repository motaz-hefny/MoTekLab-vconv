"""
Logging Setup Module

Configures application logging with rotation and multiple handlers.
"""

import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(
    level: int = logging.INFO,
    log_file: str = None,
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 3
) -> logging.Logger:
    """
    Setup application logging with console and file handlers.

    Args:
        level: Logging level
        log_file: Custom log file path (default: ~/.config/vconv/logs/vconv.log)
        max_bytes: Max log file size before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger
    """
    # Create log directory
    if log_file is None:
        log_dir = Path.home() / ".config" / "vconv" / "logs"
    else:
        log_dir = Path(log_file).parent

    log_dir.mkdir(parents=True, exist_ok=True)

    if log_file is None:
        log_file = str(log_dir / "vconv.log")

    # Create logger
    logger = logging.getLogger("vconv")
    logger.setLevel(level)

    # Only configure once — return existing logger if already set up
    if logger.handlers:
        logger.setLevel(level)
        return logger

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '[%(levelname)s] %(message)s'
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(simple_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Log startup
    logger.info(f"Logging initialized - level: {logging.getLevelName(level)}")
    logger.debug(f"Log file: {log_file}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f"vconv.{name}")


# Context manager for temporary debug logging
class DebugContext:
    """Temporary enable debug logging."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.original_level = None

    def __enter__(self):
        self.original_level = self.logger.level
        self.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)


# Log rotation check
def check_log_rotation(log_file: str = None):
    """Check if log files need rotation."""
    if log_file is None:
        log_file = str(Path.home() / ".config" / "vconv" / "logs" / "vconv.log")

    log_path = Path(log_file)
    if log_path.exists():
        size_mb = log_path.stat().st_size / (1024 * 1024)
        return size_mb > 10  # Warn if > 10MB

    return False


if __name__ == "__main__":
    # Test logging
    logger = setup_logging(logging.DEBUG)
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")

    # Get module logger
    mod_logger = get_logger(__name__)
    mod_logger.info("Module logger test")