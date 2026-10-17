"""Seeker SDK core."""

from . import plugins
from .errors import ConfigError, PluginError, SeekerError, SourceError, TranscriptError
from .masterlist import (MasterList, Video, merge_manual, new_video, retry_delay_days, sort_newest_first, today,
                         transcript_waiting)
from .settings import DEFAULT_CHANNEL_URL, DEFAULT_MASTER_FILE, env

__all__ = [
    "ConfigError", "PluginError", "SeekerError", "SourceError", "TranscriptError",
    "MasterList", "Video", "merge_manual", "new_video", "retry_delay_days", "sort_newest_first", "today",
    "transcript_waiting",
    "DEFAULT_CHANNEL_URL", "DEFAULT_MASTER_FILE", "env", "plugins",
]
__version__ = "0.1.0"
