"""Seeker SDK transcripts."""

from .config import FINAL_FORMATS, SOURCE_FORMATS, Network, TranscriptConfig, parse_finals
from .formats import Cue, parse_cues, primary_path, produce_finals, render, transcript_path
from .methods.base import TranscriptMethod
from .methods.ytdlp import pick_language
from .service import (BatchResult, FileDiff, MethodOutcome, compare, diff_outcomes, download_many, get_method,
                      link, method_names)

__all__ = [
    "BatchResult", "Cue", "FINAL_FORMATS", "FileDiff", "MethodOutcome", "Network", "SOURCE_FORMATS",
    "TranscriptConfig", "TranscriptMethod", "compare", "diff_outcomes", "download_many", "get_method", "link",
    "method_names", "parse_cues", "parse_finals", "pick_language", "primary_path", "produce_finals", "render",
    "transcript_path",
]
__version__ = "0.1.0"
