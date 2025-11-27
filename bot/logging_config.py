"""
Comprehensive logging configuration for WompBot

Provides structured logging with different levels and formatters
for console and file output.
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }

    def format(self, record):
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"

        # Format the message
        formatted = super().format(record)

        # Reset levelname for other handlers
        record.levelname = levelname

        return formatted


def setup_logging(log_level: str = "INFO", log_dir: str = "/app/logs"):
    """
    Configure comprehensive logging for the bot

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
    """
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_formatter = ColoredFormatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler for all logs (rotating)
    all_log_file = log_path / "wompbot.log"
    file_handler = RotatingFileHandler(
        all_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # Capture everything in file
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Error log file (only errors and critical)
    error_log_file = log_path / "errors.log"
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)

    # Command log file (for tracking command usage)
    command_log_file = log_path / "commands.log"
    command_handler = RotatingFileHandler(
        command_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding='utf-8'
    )
    command_handler.setLevel(logging.INFO)
    command_handler.setFormatter(file_formatter)

    # Create command logger
    command_logger = logging.getLogger('commands')
    command_logger.addHandler(command_handler)
    command_logger.propagate = True  # Also log to root logger

    # Reduce noise from discord.py
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.INFO)

    # Reduce noise from other libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    root_logger.info(f"Logging system initialized (level={log_level}, dir={log_dir})")
    root_logger.info(f"Log files: {all_log_file}, {error_log_file}, {command_log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_command(user_id: int, guild_id: int, command: str, args: str = ""):
    """
    Log a command execution

    Args:
        user_id: Discord user ID
        guild_id: Discord guild (server) ID
        command: Command name
        args: Command arguments
    """
    logger = logging.getLogger('commands')
    logger.info(f"User={user_id} Guild={guild_id} Command=/{command} Args={args}")


def log_error(error: Exception, context: str = ""):
    """
    Log an error with context

    Args:
        error: The exception that occurred
        context: Additional context about where/why the error occurred
    """
    logger = logging.getLogger('errors')
    if context:
        logger.error(f"{context}: {type(error).__name__}: {error}", exc_info=True)
    else:
        logger.error(f"{type(error).__name__}: {error}", exc_info=True)


def log_database_operation(operation: str, table: str, duration_ms: float = None, success: bool = True):
    """
    Log a database operation

    Args:
        operation: Type of operation (SELECT, INSERT, UPDATE, DELETE, etc.)
        table: Table name
        duration_ms: Operation duration in milliseconds
        success: Whether the operation succeeded
    """
    logger = logging.getLogger('database')
    status = "✓" if success else "✗"
    duration_str = f" ({duration_ms:.2f}ms)" if duration_ms is not None else ""
    logger.debug(f"{status} {operation} on {table}{duration_str}")
