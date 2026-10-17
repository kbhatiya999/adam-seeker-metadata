"""Processing strategies (entry-point group `seeker.processing_strategies`): one video's transcript -> passages.

A strategy is named and versioned; its output lives in its own folder (`<name>@<version>`), so a tweaked version
sits next to the old one and the evaluation decides which is better. Strategies that need a language model call
tools through a ToolRunner and return Waiting while answers are outstanding; running again continues.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from seeker_sdk_llm import Pending, Tool, ToolRunner, Waiting, read_prompt

from .model import Passage, hms, seconds
from .windows import plain_text, timed_text, windows


@dataclass
class Processed:
    passages: List[Passage]
    files: Dict[str, str] = field(default_factory=dict)  # extra files, relative to the strategy folder


class ProcessingStrategy:
    name = ""
    version = "v1"
    description = ""
    uses_llm = False

    def settings(self) -> Dict[str, Any]:
        return {}

    def process_video(self, video: Dict[str, Any], srt_path: str,
                      runner: Optional[ToolRunner] = None) -> Union[Processed, Waiting]:
        raise NotImplementedError


class ChunksStrategy(ProcessingStrategy):
    """Baseline without a model: the raw caption text in fixed windows."""
    name = "chunks"
    version = "v1"
    description = "raw caption text in 3-minute windows (no model)"

    def __init__(self, window_seconds: float = 180):
        self.window_seconds = window_seconds

    def settings(self):
        return {"window_seconds": self.window_seconds}

    def process_video(self, video, srt_path, runner=None):
        passages = [
            Passage(f"{video['video_id']}#c{i:04d}", video["video_id"], start, end, plain_text(lines),
                    video.get("title", ""), "chunk")
            for i, (start, end, lines) in enumerate(windows(srt_path, self.window_seconds))
        ]
        return Processed(passages)


NOTE_KINDS = ["claim", "argument", "counter", "reference", "story", "question", "other"]
SPEAKERS = ["host", "guest", "caller", "viewer", "unknown"]
NOTES_TOOL = Tool("english_notes", "v1", read_prompt("seeker_sdk_knowledge", "english_notes_v1.md"), {
    "type": "object", "required": ["notes"],
    "properties": {"notes": {"type": "array", "items": {
        "type": "object", "required": ["start", "kind", "speaker", "text"],
        "properties": {
            "start": {"type": "string"},
            "kind": {"type": "string", "enum": NOTE_KINDS},
            "speaker": {"type": "string", "enum": SPEAKERS},
            "text": {"type": "string"},
            "refs": {"type": "array", "items": {"type": "string"}},
            "topics": {"type": "array", "items": {"type": "string"}},
        }}}},
})
_HMS = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")


class EnglishNotesStrategy(ProcessingStrategy):
    """A model turns each window into attributed English notes with references and times (not a translation)."""
    name = "english-notes"
    version = "v1"
    description = "English notes per 15-minute window: claims, arguments, references, with times (model)"
    uses_llm = True

    def __init__(self, window_seconds: float = 900, tool: Tool = NOTES_TOOL):
        self.window_seconds, self.tool = window_seconds, tool

    def settings(self):
        return {"window_seconds": self.window_seconds, "tool": self.tool.key}

    def process_video(self, video, srt_path, runner=None):
        if runner is None:
            raise ValueError(f"{self.name} needs a ToolRunner (it uses a language model)")
        results, waiting = [], 0
        for start, end, lines in windows(srt_path, self.window_seconds):
            output = runner.call(self.tool, {
                "video_id": video["video_id"], "title": video.get("title", ""),
                "window": {"start": hms(start), "end": hms(end)}, "transcript": timed_text(lines)})
            if isinstance(output, Pending):
                waiting += 1
            else:
                results.append((start, end, output["notes"]))
        if waiting:
            return Waiting(waiting)
        passages: List[Passage] = []
        for start, end, notes in results:
            for note in notes:
                at = seconds(note["start"]) if _HMS.match(note["start"].strip()) else start
                at = min(max(at, start), end)  # a time outside its window is a mistake; keep it inside
                refs, topics = note.get("refs", []), note.get("topics", [])
                text = note["text"] + (f" References: {'; '.join(refs)}." if refs else "") + \
                    (f" Topics: {', '.join(topics)}." if topics else "")
                passages.append(Passage(f"{video['video_id']}#n{len(passages):04d}", video["video_id"], at, at,
                                        text, video.get("title", ""), note["kind"],
                                        {"speaker": note["speaker"], "refs": refs, "topics": topics}))
        passages.sort(key=lambda p: p.start)
        for i, p in enumerate(passages):  # a note lasts until the next one starts
            p.end = passages[i + 1].start if i + 1 < len(passages) else p.start + 60
        return Processed(passages, {f"notes/{video['video_id']}.md": self._markdown(video, passages)})

    def _markdown(self, video, passages: List[Passage]) -> str:
        lines = [f"# {video.get('title', '')} ({video['video_id']})", "",
                 f"{self.name}@{self.version}, notes by {self.tool.key}", ""]
        for p in passages:
            lines.append(f"- [{p.when}]({p.link}) **{p.meta['speaker']}, {p.kind}**: {p.text}")
        return "\n".join(lines) + "\n"
