import json
import logging
import os

import pytest

from seeker_cli.main import build_parser, main
from seeker_sdk_core import masterlist, new_video, plugins
from seeker_sdk_transcripts import TranscriptMethod
from seeker_sdk_videos import VideoSource


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the commands write logs/ relative to the working directory
    monkeypatch.setattr(masterlist, "today", lambda: "2026-01-02")
    for name in ("MASTER_LIST_METHOD", "YOUTUBE_API_KEY", "TRANSCRIPT_METHOD", "TRANSCRIPT_FORMAT", "TRANSCRIPT_FINAL"):
        monkeypatch.delenv(name, raising=False)


def write_master(videos):
    with open("m.json", "w") as f:
        json.dump({"videos": videos, "last_updated": "d", "total_videos": len(videos), "channel_url": "u"}, f)


def v(video_id, date="2026-01-01", **extra):
    return {**new_video(video_id, f"title {video_id}", date, "desc"), **extra}


def test_parser_has_the_expected_commands():
    p = build_parser()
    assert p.parse_args(["videos", "update"]).func.__name__ == "cmd_update"
    assert p.parse_args(["videos", "rebuild", "--force", "--no-preserve"]).no_preserve
    assert p.parse_args(["transcripts", "--method", "ytdlp", "download", "abc"]).video_id == "abc"
    assert p.parse_args(["plugins"]).func.__name__ == "_plugins"


def test_plugins_command_lists_installed_plugins(capsys):
    with pytest.raises(SystemExit) as e:
        main(["plugins"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "seeker.video_sources" in out and "youtube_api" in out and "seeker.transcript_methods" in out


def test_manage_report_and_categorize(capsys):
    write_master([v("a"), v("b")])
    with pytest.raises(SystemExit):
        main(["videos", "manage", "--master-file", "m.json", "categorize", "a", "--categories", "x, y", "--relevance", "9"])
    assert "categorized successfully" in capsys.readouterr().out
    saved = json.load(open("m.json"))["videos"][0]
    assert saved["categories"] == ["x", "y"] and saved["relevance_score"] == 9
    with pytest.raises(SystemExit):
        main(["videos", "manage", "--master-file", "m.json", "report"])
    out = capsys.readouterr().out
    assert "VIDEO LIST REPORT" in out and "categorized: 1" in out and "uncategorized: 1" in out
    with pytest.raises(SystemExit):
        main(["videos", "manage", "--master-file", "m.json", "categorize", "zzz", "--categories", "x"])
    assert "not found" in capsys.readouterr().out


class Source(VideoSource):
    name = "cli_fake"
    recent = [new_video("newnewnew11", "fresh", "2026-02-01", "d")]

    def channel_id(self, channel_url):
        return "UC"

    def fetch_recent(self, channel_id, limit=50):
        return list(self.recent)

    def fetch_all(self, channel_id):
        return list(self.recent) + [new_video("a", "t", "2026-01-01", "d")]


def test_update_through_the_cli_with_an_explicit_plugin_method(monkeypatch, caplog):
    write_master([v("a")])
    plugins.register(plugins.VIDEO_SOURCES, "cli_fake", Source)
    monkeypatch.setenv("MASTER_LIST_METHOD", "cli_fake")
    try:
        with caplog.at_level("INFO"), pytest.raises(SystemExit) as e:
            main(["videos", "update", "--master-file", "m.json"])
    finally:
        plugins.unregister(plugins.VIDEO_SOURCES, "cli_fake")
    assert e.value.code == 0
    assert [x["video_id"] for x in json.load(open("m.json"))["videos"]] == ["newnewnew11", "a"]
    text = caplog.text
    assert "MASTER_LIST_METHOD=cli_fake (explicit, no fallback)" in text
    assert "🆕 New: fresh (2026-02-01)" in text and "Successfully added 1 new videos" in text  # the workflow reads these


def test_explicit_method_without_key_exits_with_the_message(monkeypatch):
    write_master([v("a")])
    monkeypatch.setenv("MASTER_LIST_METHOD", "youtube_api")
    with pytest.raises(SystemExit) as e:
        main(["videos", "update", "--master-file", "m.json"])
    assert "YOUTUBE_API_KEY is not set" in str(e.value.code)


def test_rebuild_through_the_cli(monkeypatch):
    write_master([v("a", categories=["keep"])])
    plugins.register(plugins.VIDEO_SOURCES, "cli_fake", Source)
    monkeypatch.setenv("MASTER_LIST_METHOD", "cli_fake")
    try:
        with pytest.raises(SystemExit) as e:
            main(["videos", "rebuild", "--master-file", "m.json", "--force"])
    finally:
        plugins.unregister(plugins.VIDEO_SOURCES, "cli_fake")
    assert e.value.code == 0
    saved = json.load(open("m.json"))
    assert [x["video_id"] for x in saved["videos"]] == ["newnewnew11", "a"] and saved["videos"][1]["categories"] == ["keep"]
    import glob
    assert glob.glob("m.json.backup_*")  # timestamped backup of the previous list


def test_transcripts_stats_and_method_is_mandatory_for_downloads(capsys):
    write_master([v("a", transcript_file="nope.srt"), v("b")])
    with pytest.raises(SystemExit):
        main(["transcripts", "--master-file", "m.json", "stats"])
    assert "Videos: 2  with transcript: 0  missing: 2" in capsys.readouterr().out
    with pytest.raises(SystemExit) as e:
        main(["transcripts", "--master-file", "m.json", "download", "abc"])
    assert "There is no default and no fallback" in str(e.value.code)
    with pytest.raises(SystemExit) as e:
        main(["transcripts", "--master-file", "m.json", "--method", "ytdlp", "--final", "docx", "download", "abc"])
    assert "finals must be" in str(e.value.code)


@pytest.fixture
def fresh_root_logger(monkeypatch):
    """pytest adds its own root handlers while a test runs, which turns logging.basicConfig into a no-op.
    Call the returned function right before the command to start from a clean root logger."""
    root = logging.getLogger()

    def start():
        monkeypatch.setattr(root, "handlers", [])
        monkeypatch.setattr(root, "level", root.level)

    yield start
    for handler in list(root.handlers):
        handler.close()


class NoCaptions(TranscriptMethod):
    name = "cli_nocaptions"

    def check(self, video_id):
        return False

    def download(self, video_id, out_dir):
        return None


def test_transcript_downloads_log_to_a_file(fresh_root_logger, monkeypatch):
    write_master([v("abc")])
    fresh_root_logger()
    plugins.register(plugins.TRANSCRIPT_METHODS, "cli_nocaptions", NoCaptions)
    monkeypatch.setenv("TRANSCRIPT_METHOD", "cli_nocaptions")
    try:
        with pytest.raises(SystemExit) as e:
            main(["transcripts", "--master-file", "m.json", "download", "abc"])
    finally:
        plugins.unregister(plugins.TRANSCRIPT_METHODS, "cli_nocaptions")
    assert e.value.code == 1  # one video had no transcript
    log = open("logs/transcripts.log", encoding="utf-8").read()
    assert "Method: cli_nocaptions (no fallback)" in log and "abc: no transcript available" in log


def test_print_only_transcript_commands_leave_no_log_file(fresh_root_logger):
    write_master([v("abc")])
    fresh_root_logger()
    with pytest.raises(SystemExit):
        main(["transcripts", "--master-file", "m.json", "stats"])
    assert not os.path.exists("logs/transcripts.log")


class FileMethod(TranscriptMethod):
    """Has no transcript for ids that start with 'n'; writes a tiny .srt for the others."""
    name = "cli_files"

    def check(self, video_id):
        return not video_id.startswith("n")

    def download(self, video_id, out_dir):
        if video_id.startswith("n"):
            return None
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{video_id}.srt")
        open(path, "w").write("x")
        return path


@pytest.fixture
def file_method():
    plugins.register(plugins.TRANSCRIPT_METHODS, "cli_files", FileMethod)
    yield
    plugins.unregister(plugins.TRANSCRIPT_METHODS, "cli_files")


def run_transcripts(*args):
    with pytest.raises(SystemExit) as e:
        main(["transcripts", "--master-file", "m.json", "--method", "cli_files", *args])
    return e.value.code


def test_repeated_download_missing_does_not_get_stuck_on_videos_without_transcripts(file_method, capsys):
    write_master([v(i) for i in ("n1", "n2", "ok1", "ok2", "ok3")])
    assert run_transcripts("download-missing", "--limit", "2") == 0  # no transcript is not a failure
    out = capsys.readouterr().out
    assert "Done: 2 downloaded, 2 without a transcript" in out and "0 errors" in out
    saved = {x["video_id"]: x for x in json.load(open("m.json"))["videos"]}
    assert saved["n1"]["transcript_status"] == "unavailable" and saved["n1"]["transcript_retry_after"] == "2026-01-03"
    assert "transcript_file" in saved["ok1"] and "transcript_file" in saved["ok2"] and "transcript_file" not in saved["ok3"]

    assert run_transcripts("download-missing", "--limit", "2") == 0  # n1 and n2 now wait: the next run moves on
    out = capsys.readouterr().out
    assert "Done: 1 downloaded, 0 without a transcript" in out
    assert "transcript_file" in {x["video_id"]: x for x in json.load(open("m.json"))["videos"]}["ok3"]


def test_stats_and_list_missing_show_the_videos_that_wait(file_method, capsys):
    write_master([v("n1"), v("ok1")])
    run_transcripts("download-missing")
    capsys.readouterr()
    run_transcripts("stats")
    assert "Videos: 2  with transcript: 1  missing: 1  (1 of them had no transcript at the last look" in capsys.readouterr().out
    run_transcripts("list-missing")
    listing = capsys.readouterr().out
    assert "n1" in listing and "[no transcript, look again after 2026-01-03]" in listing


def test_asking_for_one_video_without_a_transcript_exits_1(file_method, capsys):
    write_master([v("n1")])
    assert run_transcripts("download", "n1") == 1
    assert "0 downloaded, 1 without a transcript" in capsys.readouterr().out
