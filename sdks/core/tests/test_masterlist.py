import json

import pytest

from seeker_sdk_core import (MasterList, SeekerError, merge_manual, new_video, retry_delay_days, sort_newest_first,
                             transcript_waiting)
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


def test_merge_keeps_old_date_and_description_when_the_fresh_ones_are_empty():
    old = [vid("a", "2026-01-01", description="old description")]
    flat = vid("a", "", description="")                     # yt-dlp flat listing: no date, no description
    full = vid("b", "2026-02-02", description="fresh")      # API: has them
    api_for_known = vid("a", "2026-03-03", description="new description")
    merged, _ = merge_manual([flat, full], old)
    assert (merged[0]["upload_date"], merged[0]["description"]) == ("2026-01-01", "old description")
    assert (merged[1]["upload_date"], merged[1]["description"]) == ("2026-02-02", "fresh")
    merged, _ = merge_manual([api_for_known], old)          # a fresh value is never overwritten
    assert (merged[0]["upload_date"], merged[0]["description"]) == ("2026-03-03", "new description")


def test_the_wait_for_a_missing_transcript_doubles_up_to_a_cap():
    assert [retry_delay_days(n) for n in range(1, 10)] == [1, 2, 4, 8, 16, 32, 64, 64, 64]
    assert retry_delay_days(0) == 1 and retry_delay_days(10_000) == 64


def test_unavailable_transcripts_wait_until_their_retry_date(tmp_path, monkeypatch):
    master = MasterList(str(tmp_path / "m.json"), {"videos": [vid("a", "2026-01-01"), vid("b", "2026-01-01")]})
    assert master.mark_transcript_unavailable("a") == "2026-01-03"
    a = master.find("a")
    assert (a["transcript_status"], a["transcript_attempts"], a["transcript_checked"]) == ("unavailable", 1, "2026-01-02")
    assert a["transcript_retry_after"] == "2026-01-03"  # today is 2026-01-02, first wait is 1 day
    ids = lambda: [v["video_id"] for v in master.videos_needing_transcript()]  # noqa: E731
    assert ids() == ["b"]                                          # a waits
    assert [v["video_id"] for v in master.videos_without_transcript()] == ["a", "b"]  # but it is still missing
    monkeypatch.setattr(masterlist, "today", lambda: "2026-01-03")
    assert ids() == ["a", "b"]                                     # on the retry date it is tried again
    assert not transcript_waiting(a) and transcript_waiting(a, on="2026-01-02")
    assert master.mark_transcript_unavailable("a") == "2026-01-05"  # second wait: 2 days
    with pytest.raises(SeekerError):
        master.mark_transcript_unavailable("zzz")


def test_linking_a_transcript_forgets_the_unavailable_notes(tmp_path):
    transcript = tmp_path / "a.srt"
    transcript.write_text("x")
    master = MasterList(str(tmp_path / "m.json"), {"videos": [vid("a", "2026-01-01")]})
    master.mark_transcript_unavailable("a")
    master.link_transcript("a", str(transcript))
    a = master.find("a")
    assert a["transcript_downloaded"] is True
    assert not any(k in a for k in ("transcript_status", "transcript_attempts", "transcript_checked", "transcript_retry_after"))


def test_a_rebuild_keeps_transcript_status_and_download_fields():
    old = [vid("a", "2026-01-01", transcript_downloaded=True, transcript_download_date="2026-01-02",
               transcript_status="unavailable", transcript_attempts=3, transcript_checked="2026-01-02",
               transcript_retry_after="2026-01-06")]
    merged, _ = merge_manual([vid("a", "2026-01-01")], old)
    a = merged[0]
    assert (a["transcript_downloaded"], a["transcript_download_date"]) == (True, "2026-01-02")
    assert (a["transcript_status"], a["transcript_attempts"], a["transcript_retry_after"]) == ("unavailable", 3, "2026-01-06")
