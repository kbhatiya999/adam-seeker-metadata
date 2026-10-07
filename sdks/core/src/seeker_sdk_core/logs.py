"""Logging setup for applications (SDKs never configure logging on import)."""

import logging
import os
from typing import Optional

FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def setup_logging(logfile: Optional[str] = None, level: int = logging.INFO) -> None:
    """Log to the console and, if given, to a file (the folder is created)."""
    handlers = [logging.StreamHandler()]
    if logfile:
        os.makedirs(os.path.dirname(logfile) or ".", exist_ok=True)
        handlers.insert(0, logging.FileHandler(logfile))
    logging.basicConfig(level=level, format=FORMAT, handlers=handlers)
