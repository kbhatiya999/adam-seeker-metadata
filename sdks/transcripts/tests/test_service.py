import json
import os

import pytest

from seeker_sdk_core import ConfigError, MasterList, TranscriptError, masterlist, plugins
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
    # the unknown id is downloaded (warned), not counted as failed; "empty" has no transcript, "blocked" is an error
    assert (result.ok, result.unavailable, result.failed) == (2, 1, 1)
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


# ---------------------------------------------------------------- videos without a transcript
def master_with(tmp_path, *ids):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"videos": [{"video_id": i} for i in ids]}))
    return MasterList.load_strict(str(path)), path


def test_a_video_without_a_transcript_is_remembered_with_a_growing_wait(tmp_path, fakes, monkeypatch):
    master, path = master_with(tmp_path, "empty")
    FakeMethod.none = {"empty"}
    method = get_method("fake", TranscriptConfig())
    for day, attempts, retry in (("2026-01-01", 1, "2026-01-02"), ("2026-01-02", 2, "2026-01-04"),
                                 ("2026-01-04", 3, "2026-01-08")):
        monkeypatch.setattr(masterlist, "today", lambda day=day: day)
        result = download_many(method, master, ["empty"], str(tmp_path / "t"))
        assert (result.ok, result.unavailable, result.failed) == (0, 1, 0)
        saved = json.loads(path.read_text())["videos"][0]  # written to disk after every change
        assert (saved["transcript_status"], saved["transcript_attempts"], saved["transcript_retry_after"]) == \
            ("unavailable", attempts, retry)
        assert saved["transcript_checked"] == day


def test_a_real_error_is_not_remembered(tmp_path, fakes):
    master, path = master_with(tmp_path, "blocked")
    FakeMethod.fail = {"blocked"}
    result = download_many(get_method("fake", TranscriptConfig()), master, ["blocked"], str(tmp_path / "t"))
    assert (result.failed, result.unavailable) == (1, 0)
    assert "transcript_status" not in json.loads(path.read_text())["videos"][0]


def test_limit_counts_downloads_so_videos_without_transcripts_cannot_use_it_up(tmp_path, fakes):
    master, path = master_with(tmp_path, "n1", "n2", "ok1", "ok2", "ok3")
    FakeMethod.none = {"n1", "n2"}
    result = download_many(get_method("fake", TranscriptConfig()), master, ["n1", "n2", "ok1", "ok2", "ok3"],
                           str(tmp_path / "t"), limit=2)
    assert (result.ok, result.unavailable, result.attempted, result.stopped) == (2, 2, 4, "")
    videos = {v["video_id"]: v for v in json.loads(path.read_text())["videos"]}
    assert "transcript_file" in videos["ok2"] and "transcript_file" not in videos["ok3"]  # ok3 was never tried


def test_max_attempts_bounds_one_run(tmp_path, fakes):
    ids = ["a", "b", "c", "d"]
    master, _ = master_with(tmp_path, *ids)
    FakeMethod.none = set(ids)
    result = download_many(get_method("fake", TranscriptConfig()), master, ids, str(tmp_path / "t"), max_attempts=3)
    assert (result.attempted, result.unavailable) == (3, 3) and "3 videos" in result.stopped


def test_the_run_stops_after_errors_in_a_row_but_a_success_resets_the_count(tmp_path, fakes):
    ids = ["e1", "e2", "fine", "e3", "e4", "e5", "e6"]
    master, _ = master_with(tmp_path, *ids)
    FakeMethod.fail = {"e1", "e2", "e3", "e4", "e5", "e6"}
    result = download_many(get_method("fake", TranscriptConfig()), master, ids, str(tmp_path / "t"))
    # e1 e2 fail, "fine" succeeds (count resets), e3 e4 e5 fail, then it stops before e6
    assert (result.ok, result.failed, result.attempted) == (1, 5, 6) and "3 errors in a row" in result.stopped


def test_finding_the_transcript_later_clears_the_unavailable_notes(tmp_path, fakes):
    master, path = master_with(tmp_path, "late")
    FakeMethod.none = {"late"}
    method = get_method("fake", TranscriptConfig())
    download_many(method, master, ["late"], str(tmp_path / "t"))
    assert master.find("late")["transcript_status"] == "unavailable"
    FakeMethod.none = set()
    assert download_many(method, master, ["late"], str(tmp_path / "t")).ok == 1
    saved = json.loads(path.read_text())["videos"][0]
    assert saved["transcript_downloaded"] is True and "transcript_status" not in saved
    assert "transcript_attempts" not in saved and "transcript_retry_after" not in saved
