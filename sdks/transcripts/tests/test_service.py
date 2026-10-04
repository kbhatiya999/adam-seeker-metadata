import json
import os

import pytest

from seeker_sdk_core import ConfigError, MasterList, TranscriptError, plugins
from seeker_sdk_transcripts import (TranscriptConfig, TranscriptMethod, compare, diff_outcomes, download_many,
                                    get_method, method_names, parse_finals, produce_finals)

TTML = ('<?xml version="1.0"?><tt xmlns="http://www.w3.org/ns/ttml"><body><div>'
        '<p begin="00:00:01.000" end="00:00:02.000">hello</p><p begin="00:00:02.000" end="00:00:03.000">world</p>'
        "</div></body></tt>")


class FakeMethod(TranscriptMethod):
    """Writes a ttml 'download' and converts it, like the real methods do."""
    name = "fake"
    text = TTML
    fail = set()
    none = set()

    def check(self, video_id):
        return video_id not in self.none

    def download(self, video_id, out_dir):
        if video_id in self.fail:
            raise TranscriptError(f"{video_id} blocked")
        if video_id in self.none:
            return None
        os.makedirs(out_dir, exist_ok=True)
        source = os.path.join(out_dir, f"{video_id}.source.ttml")
        open(source, "w", encoding="utf-8").write(self.text)
        produce_finals(source, os.path.join(out_dir, video_id), self.config.finals, self.config.keep_source)
        from seeker_sdk_transcripts import primary_path
        return primary_path(out_dir, video_id, self.config.finals)


@pytest.fixture
def fakes():
    plugins.register(plugins.TRANSCRIPT_METHODS, "fake", FakeMethod)
    other = type("Other", (FakeMethod,), {"name": "other"})
    plugins.register(plugins.TRANSCRIPT_METHODS, "other", other)
    yield
    plugins.unregister(plugins.TRANSCRIPT_METHODS, "fake")
    plugins.unregister(plugins.TRANSCRIPT_METHODS, "other")
    FakeMethod.fail, FakeMethod.none, FakeMethod.text = set(), set(), TTML


def test_config_validation():
    assert TranscriptConfig().source_format == "ttml" and TranscriptConfig().finals == ("srt", "txt")
    with pytest.raises(ConfigError):
        TranscriptConfig(source_format="mp3")
    with pytest.raises(ConfigError):
        TranscriptConfig(finals=("srt", "docx"))
    with pytest.raises(ConfigError):
        TranscriptConfig(finals=())
    assert parse_finals(" srt, txt,srt ,") == ("srt", "txt")


def test_real_methods_are_discovered_and_instantiated():
    assert {"ytdlp", "youtube_transcript_api"} <= set(method_names())
    assert get_method("ytdlp").name == "ytdlp" and get_method("youtube_transcript_api").name == "youtube_transcript_api"


def test_download_many_links_saves_and_counts(tmp_path, fakes):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"videos": [{"video_id": "ok"}, {"video_id": "blocked"}, {"video_id": "empty"}]}))
    master = MasterList.load_strict(str(path))
    FakeMethod.fail, FakeMethod.none = {"blocked"}, {"empty"}
    method = get_method("fake", TranscriptConfig(finals=("srt", "txt")))
    result = download_many(method, master, ["ok", "blocked", "empty", "not-in-master-but-fine"], str(tmp_path / "t"))
    assert (result.ok, result.failed) == (2, 2)  # the unknown id is downloaded (warned), not counted as failed
    saved = json.loads(path.read_text())["videos"][0]
    assert saved["transcript_file"].endswith("ok.srt") and saved["transcript_text_file"].endswith("ok.txt")
    assert saved["transcript_downloaded"] is True
    assert open(saved["transcript_text_file"], encoding="utf-8").read() == "hello world\n"
    assert not os.path.exists(tmp_path / "t" / "ok.source.ttml")  # source removed unless keep_source


def test_keep_source_and_finals_choice(tmp_path, fakes):
    cfg = TranscriptConfig(finals=("vtt",), keep_source=True)
    produce_finals_path = get_method("fake", cfg).download("v", str(tmp_path))
    assert produce_finals_path.endswith("v.vtt") and (tmp_path / "v.source.ttml").exists()
    assert not (tmp_path / "v.srt").exists() and not (tmp_path / "v.txt").exists()


def test_compare_runs_each_method_independently_and_diffs(tmp_path, fakes):
    cfg = TranscriptConfig(finals=("srt", "txt"))
    outcomes = compare("vid", cfg, ["fake", "other"], str(tmp_path))
    assert [o.status for o in outcomes] == ["ok", "ok"] and outcomes[0].words == 2
    assert outcomes[0].files["srt"].endswith(os.path.join("compare", "vid", "fake", "vid.srt"))
    assert all(d.identical for d in diff_outcomes(*outcomes))

    class Different(FakeMethod):
        name = "different"
        text = TTML.replace("world", "there")

    plugins.register(plugins.TRANSCRIPT_METHODS, "different", Different)
    try:
        outcomes = compare("vid2", cfg, ["fake", "different"], str(tmp_path))
        diffs = {d.ext: d for d in diff_outcomes(*outcomes)}
        assert not diffs["txt"].identical and any("there" in line for line in diffs["txt"].changed)
    finally:
        plugins.unregister(plugins.TRANSCRIPT_METHODS, "different")


def test_compare_reports_a_failing_method_without_falling_back(tmp_path, fakes):
    FakeMethod.fail = {"vid"}
    outcomes = compare("vid", TranscriptConfig(), ["fake"], str(tmp_path))
    assert outcomes[0].status == "failed" and "blocked" in outcomes[0].detail
    FakeMethod.fail, FakeMethod.none = set(), {"vid"}
    assert compare("vid", TranscriptConfig(), ["fake"], str(tmp_path))[0].status == "none"
