from __future__ import annotations

import json
import logging


LOGGER_NAME = "credit_assessment"


def configure_logging(level: int = logging.INFO) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)


def log_event(event: str, **fields: object) -> None:
    logging.getLogger(LOGGER_NAME).info(
        json.dumps({"event": event, **fields}, ensure_ascii=False, default=str, sort_keys=True)
    )

