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


def test_no_cookies_means_no_cookiefile_option():
    assert "cookiefile" not in _method()._base_opts()


@pytest.mark.parametrize("value", ["not base64 !!", "   "])
def test_bad_base64_is_a_clear_error(value):
    from seeker_sdk_core import TranscriptError
    with pytest.raises(TranscriptError, match="YTDLP_COOKIES_BASE64"):
        _method(cookies_base64=value)._base_opts()


BOT = "ERROR: [youtube] abc: Sign in to confirm you\u2019re not a bot. Use --cookies-from-browser"


class Flaky:
    """A fake YoutubeDL that is blocked `blocked` times, then answers."""
    blocked = 0
    calls = 0

    def __init__(self, opts=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        Flaky.calls += 1
        if Flaky.calls <= Flaky.blocked:
            raise RuntimeError(BOT)
        return MANUAL


def _flaky(monkeypatch, blocked, **network):
    Flaky.blocked, Flaky.calls = blocked, 0
    monkeypatch.setattr(ytdlp_module.yt_dlp, "YoutubeDL", Flaky)
    m = _method(**network)
    m.RETRY_PAUSE = 0
    return m


def test_a_blocked_proxy_address_is_retried(monkeypatch):
    m = _flaky(monkeypatch, 3, proxy="http://p:80/")
    assert m.check("abc") is True and Flaky.calls == 4


def test_gives_up_after_the_retries(monkeypatch):
    from seeker_sdk_core import TranscriptError
    m = _flaky(monkeypatch, 99, proxy="http://p:80/", proxy_retries=2)
    with pytest.raises(TranscriptError, match="Sign in to confirm"):
        m.check("abc")
    assert Flaky.calls == 3


def test_no_retry_without_a_proxy_the_address_would_be_the_same(monkeypatch):
    from seeker_sdk_core import TranscriptError
    m = _flaky(monkeypatch, 1)
    with pytest.raises(TranscriptError):
        m.check("abc")
    assert Flaky.calls == 1


def test_other_errors_are_not_retried(monkeypatch):
    from seeker_sdk_core import TranscriptError
    m = _flaky(monkeypatch, 0, proxy="http://p:80/")
    monkeypatch.setattr(Flaky, "extract_info", lambda self, url, download=False: (_ for _ in ()).throw(RuntimeError("Video unavailable")))
    with pytest.raises(TranscriptError, match="Video unavailable"):
        m.check("abc")
