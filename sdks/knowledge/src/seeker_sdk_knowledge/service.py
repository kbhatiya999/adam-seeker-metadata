"""Run a processing strategy over the videos that have transcripts."""

import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from seeker_sdk_core import MasterList, plugins
from seeker_sdk_llm import ToolRunner, Waiting

from .store import KnowledgeStore
from .strategies import ProcessingStrategy

DEFAULT_TRANSCRIPTS_DIR = "data/transcripts"


def strategy_names() -> List[str]:
    return plugins.names(plugins.PROCESSING_STRATEGIES)


def get_strategy(name: str, **settings) -> ProcessingStrategy:
    return plugins.load(plugins.PROCESSING_STRATEGIES, name)(**settings)


@dataclass
class ProcessReport:
    done: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)        # already processed (use force to redo)
    waiting: Dict[str, int] = field(default_factory=dict)   # video -> tool answers still outstanding
    no_transcript: List[str] = field(default_factory=list)


def process(strategy: ProcessingStrategy, master: MasterList, store: KnowledgeStore,
            runner: Optional[ToolRunner] = None, videos: Optional[Iterable[str]] = None,
            transcripts_dir: str = DEFAULT_TRANSCRIPTS_DIR, force: bool = False) -> ProcessReport:
    """Process the chosen videos (all by default). Safe to run again: done videos are skipped, waiting ones continue."""
    wanted = list(videos) if videos else None
    report = ProcessReport()
    for video in master.videos:
        vid = video["video_id"]
        if wanted is not None and vid not in wanted:
            continue
        srt = os.path.join(transcripts_dir, f"{vid}.srt")
        if not os.path.exists(srt):
            if wanted is not None:
                report.no_transcript.append(vid)
            continue
        if store.has(vid) and not force:
            report.skipped.append(vid)
            continue
        result = strategy.process_video(video, srt, runner)
        if isinstance(result, Waiting):
            report.waiting[vid] = result.requests
            continue
        settings = {**strategy.settings(), **({"provider": runner.provider.key} if runner is not None else {})}
        store.write(vid, result.passages, result.files, settings)
        report.done.append(vid)
    return report
