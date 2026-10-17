"""Text-file store: data/knowledge/<strategy>@<version>/

    passages/<video_id>.jsonl   the passages chat strategies search (one JSON object per line)
    notes/<video_id>.md         readable output, for strategies that make one (english-notes)
    manifest.json               strategy, version, settings and which videos are done
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .model import Passage

DEFAULT_KNOWLEDGE_DIR = "data/knowledge"


class KnowledgeStore:
    def __init__(self, root: str, strategy: str, version: str):
        self.dir = Path(root) / f"{strategy}@{version}"
        self.strategy, self.version = strategy, version

    def _passages_file(self, video_id: str) -> Path:
        return self.dir / "passages" / f"{video_id}.jsonl"

    def has(self, video_id: str) -> bool:
        return self._passages_file(video_id).exists()

    def videos(self) -> List[str]:
        folder = self.dir / "passages"
        return sorted(p.stem for p in folder.glob("*.jsonl")) if folder.exists() else []

    def manifest(self) -> Dict[str, Any]:
        path = self.dir / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def write(self, video_id: str, passages: List[Passage], files: Optional[Dict[str, str]] = None,
              settings: Optional[Dict[str, Any]] = None) -> None:
        path = self._passages_file(video_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(p.to_dict(), ensure_ascii=False) + "\n" for p in passages),
                        encoding="utf-8")
        for name, content in (files or {}).items():
            target = self.dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        manifest = self.manifest() or {"strategy": self.strategy, "version": self.version, "videos": {}}
        manifest["settings"] = settings or manifest.get("settings", {})
        manifest["videos"][video_id] = {"passages": len(passages), "done": datetime.now().isoformat(timespec="seconds")}
        (self.dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def passages(self, videos: Optional[Iterable[str]] = None) -> List[Passage]:
        wanted = set(videos) if videos else None
        out: List[Passage] = []
        for video_id in self.videos():
            if wanted is None or video_id in wanted:
                with open(self._passages_file(video_id), encoding="utf-8") as f:
                    out += [Passage.from_dict(json.loads(line)) for line in f if line.strip()]
        return out
