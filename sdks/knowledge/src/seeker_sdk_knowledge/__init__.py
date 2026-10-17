"""Seeker SDK knowledge: processing strategies that turn transcripts into searchable passages, stored as text files."""

from .model import Passage, hms, seconds
from .service import DEFAULT_TRANSCRIPTS_DIR, ProcessReport, get_strategy, process, strategy_names
from .store import DEFAULT_KNOWLEDGE_DIR, KnowledgeStore
from .strategies import NOTES_TOOL, ChunksStrategy, EnglishNotesStrategy, ProcessingStrategy, Processed
from .windows import timed_text, windows

__all__ = [
    "DEFAULT_KNOWLEDGE_DIR", "DEFAULT_TRANSCRIPTS_DIR", "NOTES_TOOL", "ChunksStrategy", "EnglishNotesStrategy",
    "KnowledgeStore", "Passage", "ProcessReport", "Processed", "ProcessingStrategy", "get_strategy", "hms",
    "process", "seconds", "strategy_names", "timed_text", "windows",
]
__version__ = "0.1.0"
