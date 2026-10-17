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
    ok: int = 0           # transcripts downloaded
    unavailable: int = 0  # the video has no transcript (yet): remembered in the master list, retried later
    failed: int = 0       # a real error (blocked, network, ...): nothing remembered, tried again next run
    attempted: int = 0
    stopped: str = ""     # why the run ended early, if it did


def link(master: MasterList, video_id: str, path: str) -> None:
    """Link a downloaded transcript (and its .txt, if present) from the master list entry."""
    txt = os.path.splitext(path)[0] + ".txt"
    master.link_transcript(video_id, path, txt if os.path.exists(txt) else None)


def download_many(method: TranscriptMethod, master: MasterList, video_ids: Iterable[str],
                  out_dir: str = DEFAULT_OUT_DIR, limit: Optional[int] = None,
                  max_attempts: Optional[int] = None, max_errors: int = 3) -> BatchResult:
    """Download the videos one at a time, never retrying with another method.

    - `limit` is the number of transcripts to download (not of videos tried): videos without a transcript
      are skipped over, so a few of them at the top of the list cannot use up the whole run.
    - A video with no transcript is remembered in the master list with a retry date that moves further
      away every time (exponential), so it is not tried again on every run.
    - A real error is logged and counted, nothing is remembered. After `max_errors` errors in a row the run
      stops, because that usually means YouTube is blocking us.
    - `max_attempts` bounds the number of videos tried in one run.
    The master list is saved after every change."""
    result = BatchResult()
    errors_in_row = 0
    for video_id in video_ids:
        if limit is not None and result.ok >= limit:
            break
        if max_attempts is not None and result.attempted >= max_attempts:
            result.stopped = f"tried {max_attempts} videos (the limit for one run)"
            break
        if errors_in_row >= max_errors:
            result.stopped = f"{max_errors} errors in a row (YouTube is probably blocking requests)"
            break
        result.attempted += 1
        try:
            path = method.download(video_id, out_dir)
        except TranscriptError as e:
            logger.error("%s: %s", video_id, e)
            result.failed += 1
            errors_in_row += 1
            continue
        errors_in_row = 0
        if not path:
            result.unavailable += 1
            if master.find(video_id):
                retry = master.mark_transcript_unavailable(video_id)
                master.write(sort=False)
                logger.warning("%s: no transcript available, will look again after %s", video_id, retry)
            else:
                logger.warning("%s: no transcript available", video_id)
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
