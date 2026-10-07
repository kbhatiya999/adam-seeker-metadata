"""Use cases: pick a method, download one or many transcripts, compare methods."""

import difflib
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from seeker_sdk_core import MasterList, TranscriptError, plugins

from .config import TranscriptConfig
from .formats import parse_cues, transcript_path
from .methods.base import TranscriptMethod

logger = logging.getLogger(__name__)

DEFAULT_OUT_DIR = "data/transcripts"


def method_names() -> List[str]:
    return plugins.names(plugins.TRANSCRIPT_METHODS)


def get_method(name: str, config: Optional[TranscriptConfig] = None) -> TranscriptMethod:
    """Instantiate a transcript method plugin by name."""
    return plugins.load(plugins.TRANSCRIPT_METHODS, name)(config or TranscriptConfig())


@dataclass
class BatchResult:
    ok: int = 0
    failed: int = 0


def link(master: MasterList, video_id: str, path: str) -> None:
    """Link a downloaded transcript (and its .txt, if present) from the master list entry."""
    txt = os.path.splitext(path)[0] + ".txt"
    master.link_transcript(video_id, path, txt if os.path.exists(txt) else None)


def download_many(method: TranscriptMethod, master: MasterList, video_ids: Iterable[str],
                  out_dir: str = DEFAULT_OUT_DIR) -> BatchResult:
    """Download each video; failures are logged and counted, never swallowed silently or retried
    with another method. The master list is saved after every success."""
    result = BatchResult()
    for video_id in video_ids:
        try:
            path = method.download(video_id, out_dir)
        except TranscriptError as e:
            logger.error("%s: %s", video_id, e)
            result.failed += 1
            continue
        if not path:
            logger.warning("%s: no transcript available", video_id)
            result.failed += 1
            continue
        try:
            link(master, video_id, path)
            master.write(sort=False)
        except Exception as e:  # e.g. a video that is not in the master list
            logger.warning("%s: transcript saved to %s but %s", video_id, path, e)
        else:
            logger.info("%s: saved %s", video_id, path)
        result.ok += 1
    return result


@dataclass
class MethodOutcome:
    method: str
    status: str                      # ok | none | failed
    detail: str = ""
    files: Dict[str, str] = field(default_factory=dict)   # final format -> path
    words: int = 0
    size_kb: int = 0


@dataclass
class FileDiff:
    ext: str
    identical: bool
    lines_a: int
    lines_b: int
    changed: List[str]


def compare(video_id: str, config: TranscriptConfig, methods: Iterable[str],
            base_dir: str = DEFAULT_OUT_DIR) -> List[MethodOutcome]:
    """Run each method independently (no fallback) into <base_dir>/compare/<id>/<method>/."""
    outcomes: List[MethodOutcome] = []
    for name in methods:
        out_dir = os.path.join(base_dir, "compare", video_id, name)
        os.makedirs(out_dir, exist_ok=True)
        try:
            path = get_method(name, config).download(video_id, out_dir)
        except TranscriptError as e:
            outcomes.append(MethodOutcome(name, "failed", str(e).strip().splitlines()[0][:70]))
            continue
        if not path:
            outcomes.append(MethodOutcome(name, "none", "no transcript available"))
            continue
        files = {ext: transcript_path(out_dir, video_id, ext) for ext in config.finals
                 if os.path.exists(transcript_path(out_dir, video_id, ext))}
        words = len(" ".join(text for _, _, text in parse_cues(path)).split())
        outcomes.append(MethodOutcome(name, "ok", files=files, words=words,
                                      size_kb=os.path.getsize(path) // 1024))
    return outcomes


def diff_outcomes(a: MethodOutcome, b: MethodOutcome) -> List[FileDiff]:
    """Diff the final files two methods produced (same format by format)."""
    diffs: List[FileDiff] = []
    for ext, path_a in a.files.items():
        path_b = b.files.get(ext)
        if not path_b:
            continue
        with open(path_a, encoding="utf-8") as fa, open(path_b, encoding="utf-8") as fb:
            lines_a, lines_b = fa.read().splitlines(), fb.read().splitlines()
        if lines_a == lines_b:
            diffs.append(FileDiff(ext, True, len(lines_a), len(lines_b), []))
            continue
        changed = [d for d in difflib.unified_diff(lines_a, lines_b, a.method, b.method, lineterm="", n=0)
                   if not d.startswith(("---", "+++", "@@"))]
        diffs.append(FileDiff(ext, False, len(lines_a), len(lines_b), changed))
    return diffs
