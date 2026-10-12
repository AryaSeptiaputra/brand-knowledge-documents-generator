"""Application logging configuration."""

import logging

from pythonjsonlogger.json import JsonFormatter

from brand_docs.settings import Settings


def setup_logger(name: str) -> logging.Logger:
    """Create a consistently formatted application logger."""
    settings = Settings()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    if settings.log_format == "json":
        # Keeps the timestamp, severity, logger name, and message in JSON logs.
        handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    else:
        # Keeps the timestamp, severity, logger name, and message in text logs.
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
