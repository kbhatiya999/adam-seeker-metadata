import json

import pytest

from seeker_sdk_core import ConfigError, MasterList, new_video, plugins
from seeker_sdk_core import masterlist
from seeker_sdk_videos import MethodChoice, SourceConfig, VideoSource, make_source, rebuild, resolve_method, update


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(masterlist, "today", lambda: "2026-01-02")


def v(video_id, date="2026-01-01"):
    return new_video(video_id, f"t {video_id}", date, "d")


class FakeSource(VideoSource):
    name = "fake"
    recent: list = []
    everything: list = []
    cid = "CHANNEL"

    def channel_id(self, channel_url):
        return self.cid

    def fetch_recent(self, channel_id, limit=50):
        return list(self.recent)

    def fetch_all(self, channel_id):
        return list(self.everything)


def make(strict=False, **attrs):
    cls = type("S", (FakeSource,), attrs)
    return cls(SourceConfig(strict=strict))


# ---------------------------------------------------------------- method resolution
def test_unset_method_is_implicit_api_if_key_else_ytdlp():
    assert resolve_method("key", {}) == MethodChoice("youtube_api", False)
    assert resolve_method(None, {}) == MethodChoice("ytdlp", False)
    assert resolve_method(None, {"MASTER_LIST_METHOD": "  "}) == MethodChoice("ytdlp", False)


def test_explicit_method_has_no_fallback():
    assert resolve_method("key", {"MASTER_LIST_METHOD": "ytdlp"}) == MethodChoice("ytdlp", True)
    with pytest.raises(ConfigError, match="YOUTUBE_API_KEY is not set"):
        resolve_method(None, {"MASTER_LIST_METHOD": "youtube_api"})
    with pytest.raises(ConfigError, match="must be one of"):
        resolve_method("key", {"MASTER_LIST_METHOD": "banana"})


def test_a_plugin_registered_elsewhere_can_be_chosen_explicitly():
    plugins.register(plugins.VIDEO_SOURCES, "fake", FakeSource)
    try:
        assert resolve_method(None, {"MASTER_LIST_METHOD": "fake"}) == MethodChoice("fake", True)
        source = make_source(MethodChoice("fake", True), api_key="ignored", channel_url="u")
        assert isinstance(source, FakeSource) and source.strict and source.config.api_key is None
    finally:
        plugins.unregister(plugins.VIDEO_SOURCES, "fake")


def test_make_source_gives_the_api_key_only_to_sources_that_need_it():
    assert make_source(MethodChoice("youtube_api", False), "key").config.api_key == "key"
    ytdlp = make_source(MethodChoice("ytdlp", True), "key", "https://x/@y")
    assert ytdlp.config.api_key is None and ytdlp.config.channel_url == "https://x/@y" and ytdlp.strict


# ---------------------------------------------------------------- update
def write_master(path, videos):
    path.write_text(json.dumps({"videos": videos, "last_updated": "2025-01-01", "total_videos": len(videos),
                                "channel_url": "u"}))


def test_update_adds_only_new_videos_sorted_with_backup(tmp_path):
    path = tmp_path / "m.json"
    write_master(path, [v("old", "2026-01-01")])
    result = update(str(path), "u", make(recent=[v("new", "2026-02-01"), v("old", "2026-01-01")]))
    assert [x["video_id"] for x in result.new_videos] == ["new"] and result.updated and result.total_videos == 2
    saved = json.loads(path.read_text())
    assert [x["video_id"] for x in saved["videos"]] == ["new", "old"] and saved["last_updated"] == "2026-01-02"
    assert (tmp_path / "m.json.backup").exists()


def test_update_with_nothing_new_is_not_updated(tmp_path):
    path = tmp_path / "m.json"
    write_master(path, [v("old")])
    result = update(str(path), "u", make(recent=[v("old")]))
    assert not result.updated and result.total_videos == 1


def test_non_strict_failures_are_soft_and_strict_ones_raise(tmp_path):
    path = tmp_path / "m.json"
    write_master(path, [v("old")])
    soft = update(str(path), "u", make(cid=None))
    assert not soft.updated  # no channel id: logged, nothing changes
    with pytest.raises(RuntimeError, match="channel ID"):
        update(str(path), "u", make(strict=True, cid=None))
    with pytest.raises(RuntimeError, match="no videos"):
        update(str(path), "u", make(strict=True, recent=[]))
    assert json.loads(path.read_text())["total_videos"] == 1  # untouched


# ---------------------------------------------------------------- rebuild
def test_rebuild_replaces_list_keeps_manual_work_and_drops_missing_videos(tmp_path):
    path = tmp_path / "m.json"
    kept = v("a", "2026-01-01")
    kept.update(categories=["x"], notes="n")
    write_master(path, [kept, v("private-now", "2025-01-01")])
    result = rebuild(str(path), "https://c/@x", make(everything=[v("b", "2026-03-01"), v("a", "2026-01-01")]))
    assert result.success and result.total_videos == 2 and result.preserved_manual
    saved = json.loads(path.read_text())
    assert [x["video_id"] for x in saved["videos"]] == ["b", "a"]
    assert saved["videos"][1]["categories"] == ["x"] and saved["videos"][1]["status"] == "categorized"
    assert saved["rebuild_reason"] == "Complete rebuild from scratch" and saved["channel_url"] == "https://c/@x"
    assert list(saved)[:6] == ["videos", "last_updated", "total_videos", "channel_url", "rebuild_date", "rebuild_reason"]


def test_rebuild_failure_modes(tmp_path):
    path = tmp_path / "m.json"
    write_master(path, [v("a")])
    assert not rebuild(str(path), "u", make(everything=[])).success
    with pytest.raises(RuntimeError):
        rebuild(str(path), "u", make(strict=True, everything=[]))
    assert json.loads(path.read_text())["total_videos"] == 1  # untouched
