import pytest

from seeker_sdk_core import MasterList, masterlist
from seeker_sdk_videos import SourceConfig, catalog
from seeker_sdk_videos.sources import base, youtube_api, ytdlp


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(masterlist, "today", lambda: "2026-01-02")


# ---------------------------------------------------------------- yt-dlp flat entries
def test_iter_video_entries_skips_channel_tabs_and_descends_playlists():
    info = {"entries": [
        {"_type": "playlist", "id": "UCchannelid", "title": "Videos", "entries": [{"id": "aaaaaaaaaaa"}, None]},
        {"id": "UC_not_a_video"},
        {"id": "bbbbbbbbbbb", "title": "ok"},
        None,
    ]}
    assert [e["id"] for e in base.iter_video_entries(info)] == ["aaaaaaaaaaa", "bbbbbbbbbbb"]
    assert list(base.iter_video_entries(None)) == []


class FakeYDL:
    calls = []
    info = {}

    def __init__(self, opts):
        FakeYDL.calls.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        FakeYDL.calls.append(url)
        return FakeYDL.info


def test_ytdlp_source_uses_flat_listing_and_builds_videos(monkeypatch):
    monkeypatch.setattr(ytdlp.yt_dlp, "YoutubeDL", FakeYDL)
    FakeYDL.calls = []
    FakeYDL.info = {"channel_id": "UCx", "entries": [{"id": "aaaaaaaaaaa", "title": "T", "duration": 61}]}
    source = ytdlp.YtDlpSource(SourceConfig(channel_url="https://www.youtube.com/@x/"))
    assert source.channel_id("https://www.youtube.com/@x/") == "UCx"
    assert FakeYDL.calls[0] == {"quiet": True, "extract_flat": True, "playlist_items": "1"}  # flat, never opens a video
    assert FakeYDL.calls[1] == "https://www.youtube.com/@x/videos"  # the tab is only used to read the channel id
    videos = source.fetch_recent("UCx", limit=3)
    assert FakeYDL.calls[-2]["playlistend"] == 3
    assert FakeYDL.calls[-1] == "https://www.youtube.com/playlist?list=UUx"  # uploads playlist: videos AND live streams
    assert videos == [{"video_id": "aaaaaaaaaaa", "title": "T", "url": "https://www.youtube.com/watch?v=aaaaaaaaaaa",
                       "upload_date": "", "duration": 61, "description": "", "status": "uncategorized",
                       "auto_detected": True, "needs_review": True, "last_checked": "2026-01-02"}]
    source.fetch_all("UCx")
    assert FakeYDL.calls[-2]["playlistend"] == 1000


def test_uploads_url_and_bad_channel_id():
    assert ytdlp.YtDlpSource.uploads_url("UCLXC98YXDDPoaVEQsWPg4ow") == \
        "https://www.youtube.com/playlist?list=UULXC98YXDDPoaVEQsWPg4ow"
    with pytest.raises(ValueError):
        ytdlp.YtDlpSource.uploads_url("PLsomething")
    # a bad id is an error in strict mode and a logged empty result otherwise
    assert ytdlp.YtDlpSource(SourceConfig(channel_url="u")).fetch_recent("PLx") == []
    with pytest.raises(ValueError):
        ytdlp.YtDlpSource(SourceConfig(channel_url="u", strict=True)).fetch_all("PLx")


def test_ytdlp_source_strict_raises_non_strict_returns_empty(monkeypatch):
    class Boom(FakeYDL):
        def extract_info(self, url, download=False):
            raise RuntimeError("blocked")

    monkeypatch.setattr(ytdlp.yt_dlp, "YoutubeDL", Boom)
    assert ytdlp.YtDlpSource(SourceConfig(channel_url="u")).fetch_recent("UCc") == []
    assert ytdlp.YtDlpSource(SourceConfig(channel_url="u")).channel_id("u") is None
    with pytest.raises(RuntimeError):
        ytdlp.YtDlpSource(SourceConfig(channel_url="u", strict=True)).fetch_recent("UCc")


# ---------------------------------------------------------------- YouTube API
class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def api_item(video_id, date):
    return {"snippet": {"resourceId": {"videoId": video_id}, "title": f"t {video_id}",
                        "publishedAt": f"{date}T10:00:00Z", "description": "d" * 600}}


def test_api_source_fetches_uploads_with_pagination(monkeypatch):
    seen = []

    def fake_get(url, params=None):
        seen.append((url.rsplit("/", 1)[1], dict(params)))
        if url.endswith("/channels"):
            return FakeResponse({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]})
        if "pageToken" not in params:
            return FakeResponse({"items": [api_item("a", "2026-01-01")], "nextPageToken": "T2"})
        return FakeResponse({"items": [api_item("b", "2026-02-01")]})

    monkeypatch.setattr(youtube_api.requests, "get", fake_get)
    source = youtube_api.YouTubeApiSource(SourceConfig(api_key="K"))
    everything = source.fetch_all("UCx")
    assert [v["video_id"] for v in everything] == ["a", "b"] and len(everything[0]["description"]) == 500
    assert everything[0]["upload_date"] == "2026-01-01" and "duration" not in everything[0]
    assert [name for name, _ in seen] == ["channels", "playlistItems", "playlistItems"]
    seen.clear()
    assert len(source.fetch_recent("UCx", limit=7)) == 1  # one page only
    assert seen[1][1]["maxResults"] == 7 and seen[1][1]["key"] == "K"


def test_api_source_channel_id_prefers_exact_title(monkeypatch):
    items = [{"snippet": {"title": "Other"}, "id": {"channelId": "UC1"}},
             {"snippet": {"title": "Adam Seeker Official"}, "id": {"channelId": "UC2"}}]
    monkeypatch.setattr(youtube_api.requests, "get", lambda url, params=None: FakeResponse({"items": items}))
    source = youtube_api.YouTubeApiSource(SourceConfig(api_key="K"))
    assert source.channel_id("https://www.youtube.com/@AdamSeekerOfficial") == "UC2"
    assert source.channel_id("https://www.youtube.com/watch") is None  # no @handle


def test_api_source_failure_modes(monkeypatch):
    def boom(url, params=None):
        raise RuntimeError("quota")

    monkeypatch.setattr(youtube_api.requests, "get", boom)
    assert youtube_api.YouTubeApiSource(SourceConfig(api_key="K")).fetch_recent("c") == []
    with pytest.raises(RuntimeError):
        youtube_api.YouTubeApiSource(SourceConfig(api_key="K", strict=True)).fetch_all("c")


# ---------------------------------------------------------------- catalog
def master_with(*videos):
    return MasterList("x.json", {"videos": list(videos), "last_updated": "d", "channel_url": "c"})


def video(video_id, **extra):
    return {"video_id": video_id, "title": video_id, "upload_date": "2026-01-01", "status": "uncategorized", **extra}


def test_categorize_priority_and_uncategorized():
    master = master_with(video("a"), video("b"))
    assert [v["video_id"] for v in catalog.list_uncategorized(master)] == ["a", "b"]
    assert catalog.categorize(master, "a", ["x", "y"], 8, "note")
    a = master.find("a")
    assert (a["categories"], a["status"], a["relevance_score"], a["notes"], a["needs_review"]) == \
        (["x", "y"], "categorized", 8, "note", False)
    assert catalog.mark_priority(master, "b", "urgent")
    assert master.find("b")["notes"] == "Priority video" and master.find("b")["relevance_score"] == 10
    assert not catalog.categorize(master, "missing", ["x"])
    assert catalog.list_uncategorized(master) == []


def test_report_numbers():
    master = master_with(video("a", status="categorized", categories=["x"], relevance_score=8),
                         video("b", relevance_score=4), video("c", upload_date="2026-05-01"))
    r = catalog.report(master)
    assert r["total"] == 3 and r["status_counts"] == {"categorized": 1, "uncategorized": 2}
    assert r["category_counts"] == {"x": 1} and r["scored"] == 2 and r["relevance_average"] == 6
    assert r["recent"][0]["video_id"] == "c"
