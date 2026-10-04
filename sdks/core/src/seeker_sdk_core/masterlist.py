"""The master video list (data/videos_master.json).

File format, key order and backup behaviour are the ones the original scripts used, so the
data in git does not change when the code around it does.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .errors import SeekerError

logger = logging.getLogger(__name__)

Video = Dict[str, Any]

# Fields copied back from the old list when a video is rebuilt (manual work, transcript links).
PRESERVED_FIELDS = ("relevance_score", "notes", "key_topics", "transcript_file", "transcript_text_file")


def today() -> str:
    """Today as YYYY-MM-DD (one place to patch in tests)."""
    return datetime.now().isoformat()[:10]


def new_video(video_id: str, title: str, upload_date: str, description: str, *,
              duration: Any = None, with_duration: bool = False) -> Video:
    """A freshly discovered video, in the key order the list has always used."""
    video: Video = {
        "video_id": video_id,
        "title": title,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "upload_date": upload_date,
    }
    if with_duration:
        video["duration"] = duration
    video.update({
        "description": description,
        "status": "uncategorized",
        "auto_detected": True,
        "needs_review": True,
        "last_checked": today(),
    })
    return video


def sort_newest_first(videos: List[Video]) -> None:
    """Newest upload first; videos without a date go last."""
    videos.sort(key=lambda v: v.get("upload_date", ""), reverse=True)


def merge_manual(new_videos: List[Video], old_videos: Iterable[Video]) -> Tuple[List[Video], int]:
    """Copy manual work (categories, scores, notes, topics, transcript links) from the old
    list onto freshly fetched videos. Returns (videos, number of categorized videos kept)."""
    old_by_id = {v["video_id"]: v for v in old_videos}
    preserved = 0
    for video in new_videos:
        old = old_by_id.get(video["video_id"])
        if not old:
            continue
        if old.get("categories"):
            video["categories"] = old["categories"]
            video["status"] = "categorized"
            video["needs_review"] = False
            preserved += 1
        for key in PRESERVED_FIELDS:
            if old.get(key):
                video[key] = old[key]
    return new_videos, preserved


class MasterList:
    def __init__(self, path: str, data: Optional[Dict[str, Any]] = None, channel_url: Optional[str] = None):
        self.path = path
        self.data: Dict[str, Any] = data if data is not None else self._empty(channel_url)

    @staticmethod
    def _empty(channel_url: Optional[str]) -> Dict[str, Any]:
        return {"videos": [], "last_updated": None, "total_videos": 0, "channel_url": channel_url}

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, path: str, channel_url: Optional[str] = None) -> "MasterList":
        """Load the list. A missing or unreadable file gives an empty list (and an error log)."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls(path, json.load(f), channel_url)
        except FileNotFoundError:
            logger.error(f"Master file {path} not found")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON: {e}")
        return cls(path, None, channel_url)

    @classmethod
    def load_strict(cls, path: str) -> "MasterList":
        """Load the list; raise if it is missing or not valid JSON."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls(path, json.load(f))
        except FileNotFoundError as e:
            raise SeekerError(f"Master file {path} not found") from e
        except json.JSONDecodeError as e:
            raise SeekerError(f"Error parsing JSON: {e}") from e

    @staticmethod
    def existing_videos(path: str) -> List[Video]:
        """Videos currently on disk (empty if the file is missing or unreadable)."""
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                videos = json.load(f).get("videos", [])
            logger.info(f"📊 Found {len(videos)} existing videos to preserve data from")
            return videos
        except Exception as e:
            logger.warning(f"⚠️ Could not load existing master list: {e}")
            return []

    # ------------------------------------------------------------------ access
    @property
    def videos(self) -> List[Video]:
        return self.data.setdefault("videos", [])

    def ids(self) -> set:
        return {v["video_id"] for v in self.videos}

    def find(self, video_id: str) -> Optional[Video]:
        return next((v for v in self.videos if v["video_id"] == video_id), None)

    def sort(self) -> None:
        sort_newest_first(self.videos)

    # ------------------------------------------------------------------ changes
    def add(self, new_videos: Iterable[Video]) -> None:
        """Append videos and refresh last_updated / total_videos."""
        self.videos.extend(new_videos)
        self.data["last_updated"] = today()
        self.data["total_videos"] = len(self.videos)

    def link_transcript(self, video_id: str, path: str, text_path: Optional[str] = None) -> None:
        video = self.find(video_id)
        if video is None:
            raise SeekerError(f"Video {video_id} not in master list")
        video["transcript_file"] = path
        if text_path:
            video["transcript_text_file"] = text_path
        video["transcript_downloaded"] = True
        video["transcript_download_date"] = today()

    def videos_without_transcript(self) -> List[Video]:
        return [v for v in self.videos if not (v.get("transcript_file") and os.path.exists(v["transcript_file"]))]

    # ------------------------------------------------------------------ saving
    def _dump(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def save(self) -> None:
        """Sort newest first and write, keeping the previous file as `<path>.backup`.
        If writing fails the backup is put back."""
        backup = f"{self.path}.backup"
        try:
            if os.path.exists(self.path):
                os.rename(self.path, backup)
            self.sort()
            self._dump(self.path)
            logger.info("Master list updated successfully")
        except Exception as e:
            logger.error(f"Error saving master list: {e}")
            if os.path.exists(backup):
                os.rename(backup, self.path)
            raise

    def write(self, sort: bool = True) -> None:
        """Write in place (no `.backup`). Rebuilds make a timestamped copy first."""
        if sort:
            self.sort()
        self._dump(self.path)

    def timestamped_backup(self) -> Optional[str]:
        """Copy the current file to `<path>.backup_<timestamp>`; None if there is nothing to copy."""
        if not os.path.exists(self.path):
            logger.info("No existing master file to backup")
            return None
        backup = f"{self.path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with open(backup, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"📦 Created backup: {backup}")
            return backup
        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            return None
