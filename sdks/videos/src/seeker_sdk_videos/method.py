"""Choosing how videos are discovered (MASTER_LIST_METHOD)."""

import logging
import os
from dataclasses import dataclass
from typing import Mapping, Optional

from seeker_sdk_core import ConfigError, plugins

from .sources.base import SourceConfig, VideoSource

logger = logging.getLogger(__name__)

ENV_VAR = "MASTER_LIST_METHOD"


@dataclass(frozen=True)
class MethodChoice:
    name: str
    explicit: bool  # explicit: no fallback and any failure is an error


def resolve_method(api_key: Optional[str], environ: Optional[Mapping[str, str]] = None) -> MethodChoice:
    """Decide how videos are discovered.

    MASTER_LIST_METHOD=<source name> is explicit: that source is used, there is NO fallback, and
    any failure is an error. If it is unset, the old implicit behaviour applies (API when a key is
    present, otherwise yt-dlp) and failures are only logged.
    """
    environ = os.environ if environ is None else environ
    name = (environ.get(ENV_VAR) or "").strip() or None
    if name is None:
        return MethodChoice("youtube_api" if api_key else "ytdlp", False)
    known = plugins.names(plugins.VIDEO_SOURCES)
    if name not in known:
        raise ConfigError(f"{ENV_VAR} must be one of {', '.join(known)} (got {name!r})")
    source_class = plugins.load(plugins.VIDEO_SOURCES, name)
    if getattr(source_class, "requires_api_key", False) and not api_key:
        raise ConfigError(
            f"{ENV_VAR}={name} but YOUTUBE_API_KEY is not set (no fallback). "
            "Set the key (mise run local:apikey:setup) or choose another method."
        )
    return MethodChoice(name, True)


def describe(choice: MethodChoice, api_key: Optional[str]) -> None:
    """Log which method was chosen and why."""
    if choice.explicit:
        logger.info(f"⚙️  {ENV_VAR}={choice.name} (explicit, no fallback)")
    else:
        logger.info(f"⚙️  {ENV_VAR} not set: using {choice.name} "
                    f"({'API key present' if api_key else 'no API key, yt-dlp fallback'})")
    if api_key:
        logger.info("🔑 YouTube API key provided")


def make_source(choice: MethodChoice, api_key: Optional[str], channel_url: Optional[str] = None) -> VideoSource:
    """Instantiate the chosen source plugin."""
    source_class = plugins.load(plugins.VIDEO_SOURCES, choice.name)
    return source_class(SourceConfig(
        api_key=api_key if getattr(source_class, "requires_api_key", False) else None,
        channel_url=channel_url,
        strict=choice.explicit,
    ))
