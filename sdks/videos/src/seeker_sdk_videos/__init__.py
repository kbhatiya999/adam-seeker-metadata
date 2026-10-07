"""Seeker SDK videos."""

from . import catalog
from .method import MethodChoice, describe, make_source, resolve_method
from .service import RebuildResult, UpdateResult, rebuild, update
from .sources.base import SourceConfig, VideoSource

__all__ = [
    "MethodChoice", "RebuildResult", "SourceConfig", "UpdateResult", "VideoSource",
    "catalog", "describe", "make_source", "rebuild", "resolve_method", "update",
]
__version__ = "0.1.0"
