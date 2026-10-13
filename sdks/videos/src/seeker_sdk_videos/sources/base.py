"""The video source plugin interface."""

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


@dataclass
class SourceConfig:
    api_key: Optional[str] = None
    channel_url: Optional[str] = None  # for sources that list by URL (yt-dlp)
    # explicit method chosen: raise on failure instead of logging and continuing
    strict: bool = False


class VideoSource:
    """Base class of video source plugins (entry-point group `seeker.video_sources`).

    A plugin sets `name`, says whether it `requires_api_key`, and implements the three methods.
    `fetch_*` return dicts shaped like `seeker_sdk_core.new_video(...)`. In `strict` mode a
    failure must be raised, otherwise logged with an empty result.
    """

    name: str = ""
    requires_api_key: bool = False
    # log wording, e.g. "Using yt-dlp for video discovery"
    discovery_label: str = ""

    def __init__(self, config: Optional[SourceConfig] = None):
        self.config = config or SourceConfig()
        self.strict = self.config.strict

    def channel_id(self, channel_url: str) -> Optional[str]:
        raise NotImplementedError

    def fetch_recent(self, channel_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def fetch_all(self, channel_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


def iter_video_entries(info: Optional[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """Yield real video entries from a yt-dlp result, descending into nested playlists.

    The bare channel URL returns its tabs (Videos, Live, Shorts) as entries; those are
    playlists, not videos, and must not be treated as videos.
    """
    for entry in (info or {}).get("entries") or []:
        if not entry:
            continue
        if entry.get("_type") == "playlist" or "entries" in entry:
            yield from iter_video_entries(entry)
        elif re.fullmatch(r"[A-Za-z0-9_-]{11}", entry.get("id") or ""):
            yield entry
