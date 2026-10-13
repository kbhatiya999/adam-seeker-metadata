"""Configuration objects for transcript downloads (no globals: pass what you want)."""

from dataclasses import dataclass, field
from typing import Optional, Tuple

from seeker_sdk_core import ConfigError

SOURCE_FORMATS = ("ttml", "srv1", "srt", "vtt")
FINAL_FORMATS = ("srt", "vtt", "txt")


@dataclass(frozen=True)
class Network:
    """Optional access helpers for networks YouTube blocks (cloud IPs)."""
    cookies_file: Optional[str] = None
    proxy: Optional[str] = None
    webshare_username: Optional[str] = None
    webshare_password: Optional[str] = None


@dataclass(frozen=True)
class TranscriptConfig:
    source_format: str = "ttml"                     # what is downloaded from YouTube
    finals: Tuple[str, ...] = ("srt", "txt")        # the files you end up with
    keep_source: bool = False                       # also keep the downloaded file
    languages: Tuple[str, ...] = ("en",)            # preferred when a method has to pick
    network: Network = field(default_factory=Network)

    def __post_init__(self) -> None:
        if self.source_format not in SOURCE_FORMATS:
            raise ConfigError(f"source format must be one of {', '.join(SOURCE_FORMATS)} (got {self.source_format!r})")
        bad = [f for f in self.finals if f not in FINAL_FORMATS]
        if bad or not self.finals:
            raise ConfigError(f"finals must be a non-empty list from {', '.join(FINAL_FORMATS)} (got {bad or 'nothing'})")


def parse_finals(value: str) -> Tuple[str, ...]:
    """'srt, txt' -> ('srt', 'txt') without duplicates."""
    return tuple(dict.fromkeys(x.strip() for x in value.split(",") if x.strip()))
