"""Manual curation of the master list: categorize, set priority, report."""

from collections import Counter
from typing import Any, Dict, List, Optional

from seeker_sdk_core import MasterList, today


def list_uncategorized(master: MasterList) -> List[Dict[str, Any]]:
    return [v for v in master.videos if v.get("status") == "uncategorized"]


def categorize(master: MasterList, video_id: str, categories: List[str],
               relevance_score: Optional[int] = None, notes: str = "") -> bool:
    """Categorize one video (in memory; call master.write(sort=False) to save). False if not found."""
    video = master.find(video_id)
    if video is None:
        return False
    video["categories"] = categories
    video["status"] = "categorized"
    video["needs_review"] = False
    video["last_checked"] = today()
    if relevance_score is not None:
        video["relevance_score"] = relevance_score
    if notes:
        video["notes"] = notes
    return True


def mark_priority(master: MasterList, video_id: str, category: str, relevance_score: int = 10) -> bool:
    """Priority = categorized with a note, immediately."""
    return categorize(master, video_id, [category], relevance_score, "Priority video")


def report(master: MasterList) -> Dict[str, Any]:
    """Numbers behind the report: totals, status/category counts, relevance, 5 newest videos."""
    videos = master.videos
    scores = [v.get("relevance_score") for v in videos if v.get("relevance_score")]
    categories = Counter(c for v in videos for c in v.get("categories", []))
    return {
        "total": len(videos),
        "last_updated": master.data.get("last_updated", "Never"),
        "channel_url": master.data.get("channel_url", "Unknown"),
        "status_counts": dict(Counter(v.get("status", "unknown") for v in videos)),
        "category_counts": dict(sorted(categories.items())),
        "relevance_average": (sum(scores) / len(scores)) if scores else None,
        "scored": len(scores),
        "recent": sorted(videos, key=lambda x: x.get("upload_date", ""), reverse=True)[:5],
    }
