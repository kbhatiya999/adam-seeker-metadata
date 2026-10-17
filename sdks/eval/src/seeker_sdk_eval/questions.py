"""Evaluation questions (eval/questions/*.toml, format in eval/README.md)."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from seeker_sdk_knowledge import seconds

DEFAULT_QUESTIONS_DIR = "eval/questions"


@dataclass
class Question:
    id: str
    question: str
    lang: str
    type: str
    answer: str
    tags: List[str] = field(default_factory=list)
    places: List[Tuple[str, float]] = field(default_factory=list)  # (video, seconds) where the answer is
    must_mention: List[str] = field(default_factory=list)
    checked_against: List[str] = field(default_factory=list)       # unanswerable: the videos searched

    @property
    def unanswerable(self) -> bool:
        return self.type == "unanswerable"

    @property
    def videos(self) -> List[str]:
        return sorted({v for v, _ in self.places})


def load(directory: str = DEFAULT_QUESTIONS_DIR) -> List[Question]:
    out: List[Question] = []
    for path in sorted(Path(directory).glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for q in data.get("question", []):
            if "expect" in q:
                places = [(e["video"], seconds(e["near"])) for e in q["expect"]]
            elif "near" in q:
                places = [(data["video"], seconds(q["near"]))]
            else:
                places = []
            out.append(Question(q["id"], q["question"], q["lang"], q["type"], q["answer"], q.get("tags", []),
                                places, q.get("must_mention", []), data.get("checked_against", [])))
    return out


def select(questions: Iterable[Question], videos: Optional[Iterable[str]] = None) -> List[Question]:
    """The questions that make sense for these videos: every place they point at is among them, and an
    unanswerable question only when all the videos were checked for it."""
    if not videos:
        return list(questions)
    wanted = set(videos)
    return [q for q in questions
            if (q.unanswerable and wanted <= set(q.checked_against))
            or (not q.unanswerable and q.places and set(q.videos) <= wanted)]
