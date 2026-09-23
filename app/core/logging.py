"""
Application-wide logging configuration.

We configure logging once, here, and every other module just does
`logger = logging.getLogger(__name__)`. This keeps log format consistent
and means we can change the output format (e.g. to JSON for production
log aggregation) in a single place later.
"""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()

    log_level = logging.DEBUG if settings.debug else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    # Quiet down noisy third-party loggers so our own logs aren't drowned out.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
