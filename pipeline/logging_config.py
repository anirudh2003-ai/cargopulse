"""Logging configuration for CargoPulse."""

from __future__ import annotations

import logging
import sys
from typing import Any


def configure_logging(
    level: str = "INFO",
) -> None:
    """Configure application-wide logging."""

    numeric_level = getattr(
        logging,
        level.upper(),
        logging.INFO,
    )

    logging.basicConfig(
        level=numeric_level,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named CargoPulse logger."""

    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    event: str,
    **fields: Any,
) -> None:
    """Write one structured key-value log event."""

    details = " ".join(
        f"{key}={value}"
        for key, value in sorted(fields.items())
    )

    if details:
        logger.info("%s %s", event, details)
    else:
        logger.info("%s", event)
