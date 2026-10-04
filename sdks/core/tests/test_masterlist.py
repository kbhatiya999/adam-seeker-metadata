import json

import pytest

from seeker_sdk_core import MasterList, SeekerError, merge_manual, new_video, sort_newest_first
from seeker_sdk_core import masterlist


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(masterlist, "today", lambda: "2026-01-02")


def vid(video_id, date, **extra):
    v = new_video(video_id, f"title {video_id}", date, "desc")
    v.update(extra)
    return v


def test_new_video_key_order_and_duration_only_when_asked():
    assert list(new_video("abc", "t", "2026-01-01", "d")) == [
        "video_id", "title", "url", "upload_date", "description", "status", "auto_detected", "needs_review", "last_checked"]
    with_duration = new_video("abc", "t", "2026-01-01", "d", duration=5, with_duration=True)
    assert list(with_duration)[3:6] == ["upload_date", "duration", "description"]
    assert with_duration["url"] == "https://www.youtube.com/watch?v=abc"


def test_sort_newest_first_puts_undated_last_and_is_stable():
    videos = [vid("a", ""), vid("b", "2026-01-01"), vid("c", "2026-03-01"), vid("d", "2026-01-01")]
    sort_newest_first(videos)
    assert [v["video_id"] for v in videos] == ["c", "b", "d", "a"]


def test_load_missing_and_bad_json_give_empty_list(tmp_path):
    missing = MasterList.load(str(tmp_path / "nope.json"), "https://example.com/@x")
    assert missing.videos == [] and missing.data["channel_url"] == "https://example.com/@x"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert MasterList.load(str(bad)).videos == []
    with pytest.raises(SeekerError):
        MasterList.load_strict(str(bad))
    with pytest.raises(SeekerError):
        MasterList.load_strict(str(tmp_path / "nope.json"))


def test_add_and_save_sorts_keeps_backup_and_format(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"videos": [vid("old", "2026-01-01")], "last_updated": "x", "total_videos": 1,
                                "channel_url": "u"}))
    master = MasterList.load(str(path))
    master.add([vid("new", "2026-02-01")])
    master.save()
    saved = json.loads(path.read_text())
    assert [v["video_id"] for v in saved["videos"]] == ["new", "old"]
    assert saved["total_videos"] == 2 and saved["last_updated"] == "2026-01-02"
    assert json.loads((tmp_path / "m.json.backup").read_text())["total_videos"] == 1  # previous file kept
    text = path.read_text()
    assert text.startswith('{\n  "videos": [') and not text.endswith("\n")  # indent=2, no trailing newline


def test_save_restores_backup_when_writing_fails(tmp_path, monkeypatch):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"videos": []}))
    master = MasterList.load(str(path))
    monkeypatch.setattr(MasterList, "_dump", lambda self, p: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        master.save()
    assert json.loads(path.read_text()) == {"videos": []}


def test_merge_manual_copies_manual_work_only_for_known_videos():
    old = [vid("a", "2026-01-01", categories=["x"], relevance_score=7, notes="n", transcript_file="t.srt",
               transcript_text_file="t.txt", key_topics=["k"]), vid("gone", "2025-01-01", categories=["y"])]
    fresh = [vid("a", "2026-01-01"), vid("b", "2026-01-02")]
    merged, preserved = merge_manual(fresh, old)
    a, b = merged
    assert preserved == 1 and a["categories"] == ["x"] and a["status"] == "categorized" and a["needs_review"] is False
    assert (a["relevance_score"], a["notes"], a["transcript_file"], a["transcript_text_file"], a["key_topics"]) == \
        (7, "n", "t.srt", "t.txt", ["k"])
    assert "categories" not in b and b["status"] == "uncategorized"


def test_link_transcript_and_missing(tmp_path):
    transcript = tmp_path / "a.srt"
    transcript.write_text("x")
    master = MasterList(str(tmp_path / "m.json"), {"videos": [vid("a", "2026-01-01"), vid("b", "2026-01-01")]})
    master.link_transcript("a", str(transcript), "a.txt")
    a = master.find("a")
    assert a["transcript_downloaded"] is True and a["transcript_text_file"] == "a.txt"
    assert [v["video_id"] for v in master.videos_without_transcript()] == ["b"]
    with pytest.raises(SeekerError):
        master.link_transcript("zzz", "p")


def test_timestamped_backup(tmp_path):
    path = tmp_path / "m.json"
    master = MasterList(str(path), {"videos": []})
    assert master.timestamped_backup() is None
    path.write_text(json.dumps({"videos": [1]}))
    backup = master.timestamped_backup()
    assert backup.startswith(str(path) + ".backup_") and json.loads(open(backup).read()) == {"videos": [1]}
