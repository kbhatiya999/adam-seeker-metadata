"""youtube-transcript-api method without the network: a fake API raises what the library raises."""

import pytest
from youtube_transcript_api import RequestBlocked, TranscriptsDisabled

from seeker_sdk_core import TranscriptError
from seeker_sdk_transcripts import TranscriptConfig
from seeker_sdk_transcripts.methods.library import TranscriptApiMethod


def method_that_raises(monkeypatch, error):
    class Api:
        def list(self, video_id):
            raise error

    monkeypatch.setattr(TranscriptApiMethod, "_api", lambda self: Api())
    return TranscriptApiMethod(TranscriptConfig())


def test_disabled_subtitles_mean_no_transcript_not_an_error(monkeypatch, tmp_path):
    method = method_that_raises(monkeypatch, TranscriptsDisabled("vid"))
    assert method.check("vid") is False
    assert method.download("vid", str(tmp_path)) is None


def test_a_blocked_request_is_a_one_line_error(monkeypatch, tmp_path):
    method = method_that_raises(monkeypatch, RequestBlocked("vid"))
    for call in (lambda: method.check("vid"), lambda: method.download("vid", str(tmp_path))):
        with pytest.raises(TranscriptError) as e:
            call()
        message = str(e.value)
        assert "RequestBlocked: YouTube is blocking requests" in message
        assert "\n" not in message and "github.com" not in message  # no multi-line message, no referral text
