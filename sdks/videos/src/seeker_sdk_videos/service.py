"""Use cases: update the master list with new videos, or rebuild it from YouTube."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from seeker_sdk_core import MasterList, merge_manual, sort_newest_first, today

from .sources.base import VideoSource

logger = logging.getLogger(__name__)


@dataclass
class UpdateResult:
    new_videos: List[Dict[str, Any]] = field(default_factory=list)
    total_videos: int = 0

    @property
    def updated(self) -> bool:
        return len(self.new_videos) > 0


@dataclass
class RebuildResult:
    success: bool
    total_videos: int = 0
    preserved_manual: bool = False
    error: Optional[str] = None
    backup_file: Optional[str] = None


def update(master_path: str, channel_url: str, source: VideoSource) -> UpdateResult:
    """Add videos that are not in the list yet. With a strict (explicit) source any failure raises."""
    logger.info("🚀 Starting video list update...")
    master = MasterList.load(master_path, channel_url)
    existing = master.ids()
    logger.info(f"📊 Current master list has {len(existing)} existing videos")

    channel_id = source.channel_id(channel_url)
    if not channel_id:
        logger.error("❌ Could not extract channel ID")
        if source.strict:
            raise RuntimeError("Could not extract channel ID")
        return UpdateResult([], len(master.videos))

    logger.info(source.discovery_label)
    fetched = source.fetch_recent(channel_id)
    if source.strict and not fetched:
        raise RuntimeError("The chosen method returned no videos (no fallback)")

    new_videos = [v for v in fetched if v["video_id"] not in existing]
    logger.info(f"🔍 Found {len(new_videos)} new videos (filtered from {len(fetched)} total)")

    master.add(new_videos)
    master.save()
    return UpdateResult(new_videos, master.data["total_videos"])


def rebuild(master_path: str, channel_url: str, source: VideoSource, preserve_manual: bool = True) -> RebuildResult:
    """Replace the list with everything YouTube returns; manual work is copied back from the old list."""
    logger.info("🚀 Starting COMPLETE master list rebuild...")
    old_videos = MasterList.existing_videos(master_path)

    channel_id = source.channel_id(channel_url)
    if not channel_id:
        logger.error("❌ Could not extract channel ID")
        if source.strict:
            raise RuntimeError("Could not extract channel ID")
        return RebuildResult(False, error="Could not extract channel ID")

    logger.info(source.discovery_label.replace("video discovery", "complete video discovery"))
    all_videos = source.fetch_all(channel_id)
    if not all_videos:
        logger.error("❌ No videos fetched")
        if source.strict:
            raise RuntimeError("The chosen method returned no videos (no fallback)")
        return RebuildResult(False, error="No videos fetched")

    if preserve_manual and old_videos:
        logger.info("🔄 Preserving manual categorizations from old videos...")
        all_videos, preserved = merge_manual(all_videos, old_videos)
        logger.info(f"✅ Preserved manual data for {preserved} videos")

    sort_newest_first(all_videos)
    master = MasterList(master_path, {
        "videos": all_videos,
        "last_updated": today(),
        "total_videos": len(all_videos),
        "channel_url": channel_url,
        "rebuild_date": today(),
        "rebuild_reason": "Complete rebuild from scratch",
    })
    try:
        master.write(sort=False)
    except Exception as e:
        logger.error(f"❌ Error saving rebuilt master list: {e}")
        return RebuildResult(False, error=str(e))
    logger.info(f"✅ Successfully rebuilt master list with {len(all_videos)} videos")
    return RebuildResult(True, len(all_videos), preserve_manual)
