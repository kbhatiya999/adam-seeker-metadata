"""The transcript method plugin interface."""

from typing import Optional

from ..config import TranscriptConfig


class TranscriptMethod:
    """Base class of transcript method plugins (entry-point group `seeker.transcript_methods`).

    A method downloads the transcript in `config.source_format`, converts it into
    `config.finals` inside `out_dir` and returns the primary file (srt, else vtt, else txt),
    or None when the video has no captions. Failures raise `seeker_sdk_core.TranscriptError`;
    there is never a fallback to another method.
    """

    name: str = ""

    def __init__(self, config: Optional[TranscriptConfig] = None):
        self.config = config or TranscriptConfig()

    def check(self, video_id: str) -> bool:
        """True if captions exist for the video (nothing is downloaded)."""
        raise NotImplementedError

    def download(self, video_id: str, out_dir: str) -> Optional[str]:
        raise NotImplementedError
