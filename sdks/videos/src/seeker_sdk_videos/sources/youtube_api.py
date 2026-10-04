"""Video source: YouTube Data API v3 (needs an API key; works from anywhere)."""

import logging
from typing import Any, Dict, List, Optional

import requests

from seeker_sdk_core import new_video

from .base import YOUTUBE_API_BASE, VideoSource

logger = logging.getLogger(__name__)


class YouTubeApiSource(VideoSource):
    name = "youtube_api"
    requires_api_key = True
    discovery_label = "🔑 Using YouTube Data API for video discovery"

    def channel_id(self, channel_url: str) -> Optional[str]:
        logger.info("🔑 Using YouTube Data API to get channel ID")
        try:
            if "@" in channel_url:
                handle = channel_url.split("@")[-1]
                response = requests.get(f"{YOUTUBE_API_BASE}/search", params={
                    "part": "snippet", "q": handle, "type": "channel", "key": self.config.api_key})
                response.raise_for_status()
                data = response.json()
                for item in data.get("items", []):
                    if item["snippet"]["title"].lower() == "adam seeker official":
                        channel_id = item["id"]["channelId"]
                        logger.info(f"✅ Found channel ID via API: {channel_id}")
                        return channel_id
                # If exact match not found, return first result
                if data.get("items"):
                    channel_id = data["items"][0]["id"]["channelId"]
                    logger.info(f"✅ Using first result channel ID via API: {channel_id}")
                    return channel_id
        except Exception as e:
            logger.error(f"❌ Error getting channel ID from API: {e}")
            if self.strict:
                raise
            return None
        return None

    def _uploads_playlist(self, channel_id: str) -> Optional[str]:
        response = requests.get(f"{YOUTUBE_API_BASE}/channels", params={
            "part": "contentDetails", "id": channel_id, "key": self.config.api_key})
        response.raise_for_status()
        data = response.json()
        if not data.get("items"):
            logger.error("❌ Channel not found or no uploads playlist")
            return None
        playlist = data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        logger.info(f"📺 Found uploads playlist: {playlist}")
        return playlist

    @staticmethod
    def _video(item: Dict[str, Any]) -> Dict[str, Any]:
        snippet = item["snippet"]
        return new_video(
            snippet["resourceId"]["videoId"],
            snippet["title"],
            snippet["publishedAt"][:10],  # YYYY-MM-DD
            snippet["description"][:500],  # truncate long descriptions
        )

    def _page(self, playlist: str, max_results: int, token: Optional[str] = None) -> Dict[str, Any]:
        params = {"part": "snippet", "playlistId": playlist, "maxResults": max_results, "key": self.config.api_key}
        if token:
            params["pageToken"] = token
        response = requests.get(f"{YOUTUBE_API_BASE}/playlistItems", params=params)
        response.raise_for_status()
        return response.json()

    def fetch_recent(self, channel_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        logger.info(f"🔑 Fetching videos using YouTube Data API v3 (max: {limit})")
        try:
            playlist = self._uploads_playlist(channel_id)
            if not playlist:
                return []
            videos = [self._video(i) for i in self._page(playlist, limit).get("items", [])]
            logger.info(f"✅ Successfully fetched {len(videos)} videos from YouTube Data API")
            return videos
        except Exception as e:
            logger.error(f"❌ Error fetching videos from YouTube API: {e}")
            if self.strict:
                raise
            return []

    def fetch_all(self, channel_id: str) -> List[Dict[str, Any]]:
        logger.info("🔑 Fetching ALL videos using YouTube Data API v3")
        videos: List[Dict[str, Any]] = []
        token: Optional[str] = None
        pages = 0
        max_pages = 20  # safety limit to prevent infinite loops
        try:
            playlist = self._uploads_playlist(channel_id)
            if not playlist:
                return []
            while token is not None or pages == 0:
                if pages >= max_pages:
                    logger.warning(f"⚠️ Reached maximum page limit ({max_pages}), stopping")
                    break
                pages += 1
                logger.info(f"📄 Fetching page {pages}...")
                data = self._page(playlist, 50, token)
                videos.extend(self._video(i) for i in data.get("items", []))
                token = data.get("nextPageToken")
                if token:
                    logger.info(f"📄 Found next page token: {token[:20]}...")
                else:
                    logger.info("📄 No more pages available")
            logger.info(f"✅ Successfully fetched {len(videos)} videos from YouTube Data API")
            return videos
        except Exception as e:
            logger.error(f"❌ Error fetching videos from YouTube API: {e}")
            if self.strict:
                raise
            return []
