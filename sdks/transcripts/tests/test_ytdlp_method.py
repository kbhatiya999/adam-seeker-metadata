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


COOKIES = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t4102444800\tLOGIN_INFO\tvalue\n"


def _method(**network):
    from seeker_sdk_transcripts.config import Network
    from seeker_sdk_transcripts.methods.ytdlp import YtDlpMethod
    return YtDlpMethod(TranscriptConfig(network=Network(**network)))


def b64(text: str) -> str:
    import base64
    return base64.b64encode(text.encode()).decode()


def test_cookies_from_base64_become_a_private_temp_file():
    import os
    import stat
    m = _method(cookies_base64=b64(COOKIES))
    path = m._base_opts()["cookiefile"]
    assert open(path).read() == COOKIES and stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert m._base_opts()["cookiefile"] == path   # written once per method
    os.remove(path)


def test_the_cookies_file_wins_over_base64(tmp_path):
    f = tmp_path / "c.txt"
    f.write_text(COOKIES)
    assert _method(cookies_file=str(f), cookies_base64=b64("other"))._base_opts()["cookiefile"] == str(f)


def test_no_cookies_means_no_cookiefile_option():
    assert "cookiefile" not in _method()._base_opts()


@pytest.mark.parametrize("value", ["not base64 !!", "   "])
def test_bad_base64_is_a_clear_error(value):
    from seeker_sdk_core import TranscriptError
    with pytest.raises(TranscriptError, match="YTDLP_COOKIES_BASE64"):
        _method(cookies_base64=value)._base_opts()
