import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Custom JSON log formatter producing structured logging output for production monitoring.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_object: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "filename": record.filename,
            "lineno": record.lineno,
        }

        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields if available
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_object.update(record.extra_data)

        return json.dumps(log_object)


def setup_logger(name: str = "bite_brew_ai", log_level: str = "INFO") -> logging.Logger:
    """
    Configures and returns a structured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Prevent duplicate handlers on re-initialization
    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    return logger


# App-wide global logger instance
logger = setup_logger()
