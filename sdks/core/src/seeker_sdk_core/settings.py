"""Defaults and tiny helpers for reading configuration from the environment."""

import os
from typing import Optional

DEFAULT_MASTER_FILE = "data/videos_master.json"
DEFAULT_CHANNEL_URL = "https://www.youtube.com/@AdamSeekerOfficial"


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Environment variable, stripped; empty or unset gives the default."""
    value = (os.getenv(name) or "").strip()
    return value or default
