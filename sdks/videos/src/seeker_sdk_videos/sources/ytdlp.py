"""Video source: yt-dlp, flat listing (no API key; works from cloud IPs like GitHub Actions).

Flat means yt-dlp reads only the channel's list page and never opens a video, because YouTube
blocks single-video requests from cloud IPs. The list gives id, title, duration and view count,
but not the upload date or description.
"""

import logging
from typing import Any, Dict, List, Optional

import yt_dlp

from seeker_sdk_core import new_video

from .base import VideoSource, iter_video_entries

logger = logging.getLogger(__name__)


class YtDlpSource(VideoSource):
    name = "ytdlp"
    requires_api_key = False
    discovery_label = "🔄 Using yt-dlp for video discovery"

    @staticmethod
    def _videos_url(channel_url: str) -> str:
        return channel_url.rstrip("/") + "/videos"

    def channel_id(self, channel_url: str) -> Optional[str]:
        logger.info("🔄 Using yt-dlp for channel ID")
        try:
            # Flat, one entry: reads the channel page only. A full extraction opens the channel's
            # first video, and YouTube answers that request from cloud IPs with
            # "Sign in to confirm you're not a bot".
            opts = {"quiet": True, "extract_flat": True, "playlist_items": "1"}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self._videos_url(channel_url), download=False)
                channel_id = info.get("channel_id")
                if channel_id:
                    logger.info(f"✅ Found channel ID via yt-dlp: {channel_id}")
                return channel_id
        except Exception as e:
            logger.error(f"❌ Error extracting channel ID with yt-dlp: {e}")
            if self.strict:
                raise
            return None

    def _fetch(self, limit: int, announce: str) -> List[Dict[str, Any]]:
        logger.info(announce)
        try:
            opts = {"quiet": True, "extract_flat": True, "playlistend": limit}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self._videos_url(self.config.channel_url or ""), download=False)
                videos = [
                    new_video(
                        entry["id"],
                        entry.get("title", "Unknown Title"),
                        entry.get("upload_date", ""),
                        entry.get("description", "")[:500],
                        duration=entry.get("duration", 0),
                        with_duration=True,
                    )
                    for entry in iter_video_entries(info)
                ]
                logger.info(f"✅ Successfully fetched {len(videos)} videos using yt-dlp")
                return videos
        except Exception as e:
            logger.error(f"❌ Error fetching videos with yt-dlp: {e}")
            if self.strict:
                raise
            return []

    def fetch_recent(self, channel_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self._fetch(limit, "🔄 Fetching videos using yt-dlp (fallback method)")

    def fetch_all(self, channel_id: str) -> List[Dict[str, Any]]:
        # Much higher limit for a complete rebuild
        return self._fetch(1000, "🔄 Fetching ALL videos using yt-dlp (fallback method)")
