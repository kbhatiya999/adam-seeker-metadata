"""Passages: the unit every processing strategy produces and every chat strategy searches."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict


def hms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02}:{s % 3600 // 60:02}:{s % 60:02}"


def seconds(text: str) -> float:
    parts = [float(p) for p in text.strip().split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


@dataclass
class Passage:
    id: str              # unique in a store, e.g. OCZ0vysB4xY#n0007
    video_id: str
    start: float         # seconds into the video
    end: float
    text: str            # what is searched and shown to the answering model
    title: str = ""
    kind: str = "text"   # chunk, or a note kind (claim, argument, reference ...)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def when(self) -> str:
        return hms(self.start)

    @property
    def link(self) -> str:
        return f"https://youtu.be/{self.video_id}?t={int(self.start)}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Passage":
        return cls(**data)
