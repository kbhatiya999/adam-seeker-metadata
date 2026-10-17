"""Scores that need no model."""

from typing import Iterable, List, Optional, Sequence, Tuple

from seeker_sdk_knowledge import Passage

TOLERANCE = 180.0  # seconds either side of `near` that still count as the right place


def mentions(item: str, text: str) -> bool:
    """`item` is alternatives separated by '|', matched case-insensitively."""
    return any(alt.strip().lower() in text.lower() for alt in item.split("|") if alt.strip())


def keyword_score(text: str, must_mention: Sequence[str]) -> Optional[float]:
    if not must_mention:
        return None
    return sum(mentions(item, text) for item in must_mention) / len(must_mention)


def retrieval_hit(retrieved: Iterable[Passage], places: List[Tuple[str, float]],
                  tolerance: float = TOLERANCE) -> Optional[float]:
    """Share of the expected places that some retrieved passage covers (same video, overlapping time)."""
    if not places:
        return None
    retrieved = list(retrieved)
    hits = sum(any(p.video_id == video and p.start <= near + tolerance and p.end >= near - tolerance
                   for p in retrieved) for video, near in places)
    return hits / len(places)
