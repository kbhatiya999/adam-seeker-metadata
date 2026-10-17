"""The yt-dlp method without the network: a fake YoutubeDL returns what YouTube would list."""

import pytest

from seeker_sdk_transcripts import TranscriptConfig
from seeker_sdk_transcripts.methods import ytdlp as ytdlp_module

LIVE_CHAT_ONLY = {"subtitles": {"live_chat": []}, "automatic_captions": {}}  # a finished live stream
AUTOMATIC = {"subtitles": {"live_chat": []}, "automatic_captions": {"hi-orig": []}}
MANUAL = {"subtitles": {"en": []}, "automatic_captions": {}}


@pytest.fixture
def listing(monkeypatch):
    """Set `listing.info` to what the fake YouTube returns."""
    class Fake:
        info: dict = {}

        def __init__(self, opts=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            return Fake.info

    monkeypatch.setattr(ytdlp_module.yt_dlp, "YoutubeDL", Fake)
    return Fake


@pytest.mark.parametrize("info, expected", [(LIVE_CHAT_ONLY, False), (AUTOMATIC, True), (MANUAL, True), ({}, False)])
def test_check_agrees_with_download_that_live_chat_is_not_captions(listing, info, expected):
    listing.info = info
    assert ytdlp_module.YtDlpMethod(TranscriptConfig()).check("abc") is expected


def test_download_reports_no_captions_as_none_not_as_an_error(listing, tmp_path):
    listing.info = LIVE_CHAT_ONLY
    assert ytdlp_module.YtDlpMethod(TranscriptConfig()).download("abc", str(tmp_path)) is None
