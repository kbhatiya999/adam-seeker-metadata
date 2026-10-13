"""Seeker SDK core."""

from . import plugins
from .errors import ConfigError, PluginError, SeekerError, SourceError, TranscriptError
from .masterlist import MasterList, Video, merge_manual, new_video, sort_newest_first, today
from .settings import DEFAULT_CHANNEL_URL, DEFAULT_MASTER_FILE, env

__all__ = [
    "ConfigError", "PluginError", "SeekerError", "SourceError", "TranscriptError",
    "MasterList", "Video", "merge_manual", "new_video", "sort_newest_first", "today",
    "DEFAULT_CHANNEL_URL", "DEFAULT_MASTER_FILE", "env", "plugins",
]
__version__ = "0.1.0"
