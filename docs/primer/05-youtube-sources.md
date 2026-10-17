# Primer 5: Where video information comes from

**You need:** a rough idea of what an API and an API key are. **Read after:** [03-plugins-and-entry-points.md](03-plugins-and-entry-points.md).
**Code:** `sdks/videos/src/seeker_sdk_videos/` (`sources/`, `method.py`, `service.py`).
**Findings with dates and numbers:** [../video-details-and-transcripts.md](../video-details-and-transcripts.md).

## The question every source answers
"Which videos does this channel have, and what are their titles, dates and lengths?"
There are five ways to ask YouTube. Two are built as plugins. The others are known, and the table says
which is which.

| Way to ask | Needs | Gives | Limits | In the code? |
|---|---|---|---|---|
| **YouTube Data API v3** | an API key | id, title, **date**, description (we keep 500 characters) | quota; no duration yet | plugin `youtube_api` |
| **yt-dlp, flat listing** of the uploads playlist | nothing | id, title, **duration**, view count | **no date, no description** | plugin `ytdlp` |
| **RSS feed** `feeds/videos.xml?channel_id=...` | nothing | date, description, exact views | **only the 15 newest videos** (about 7 weeks for this channel) | not built, planned |
| yt-dlp **per video** (a normal, non-flat run) | nothing | everything | **blocked from cloud IPs** ("Sign in to confirm you're not a bot") | not used for listing |
| the channel's `/videos` **tab** | nothing | the regular uploads | misses live streams: it showed 58 of 194 videos | only to read the channel id |

## Three ideas you need

**1. The uploads playlist.** Every channel has a hidden playlist with all its public uploads: regular
videos, live streams and shorts. Its id is the channel id with `UC` changed to `UU`
(`UCLXC98Y...` becomes `UULXC98Y...`). Both plugins read this playlist. In the API it comes from
`channels.list`. In yt-dlp it is `uploads_url()` in `sources/ytdlp.py`.

**2. "Flat" extraction.** Normally yt-dlp opens every video page. With `extract_flat` it only reads the
list page. That matters because YouTube refuses the per-video request from cloud IPs such as GitHub
Actions, but still serves list pages. So flat works on GitHub and a normal run does not. We found this
by testing from a real runner. Even asking for the channel id must be flat and for one entry
(`playlist_items="1"`), because a full extraction opens the first video and gets blocked.

**3. Strict or not.** `resolve_method` in `method.py` decides how we got here:

| `MASTER_LIST_METHOD` | Meaning |
|---|---|
| set to a name | **explicit**: that source only, no fallback, and any failure raises an error (exit code 1) |
| not set | **implicit**: the API if a key exists, otherwise yt-dlp, and failures are only logged |

The chosen mode becomes `source.strict`. Inside a plugin that means "raise instead of returning an
empty list". `update` and `rebuild` in `service.py` also raise when a strict source returns no videos.

## What each plugin really does

**`youtube_api`** (`sources/youtube_api.py`)
- Finds the channel id with `search` (a call that costs 100 quota units), then reads the uploads playlist
  with `playlistItems` (1 unit per page of 50). The default quota is 10,000 units a day, so a daily
  update is cheap, but a bug that loops over `search` is not.
- `fetch_recent` reads one page (the 50 newest). `fetch_all` pages until the end, with a safety stop at
  20 pages (1,000 videos).
- The channel title `"adam seeker official"` is hard-coded for the exact match in `channel_id`. For
  another channel it falls back to the first search result.

**`ytdlp`** (`sources/ytdlp.py`)
- `fetch_recent` takes the 50 newest of the uploads playlist. `fetch_all` takes up to 1,000.
- `iter_video_entries` (in `sources/base.py`) filters the result to real videos: a bare channel URL
  returns its tabs (Videos, Live, Shorts) as entries, and those are playlists, not videos.
- The listing has **no `upload_date`**, so new videos get `""`. They sort to the bottom of the list until
  someone fills the date. A rebuild keeps the date of videos that already had one; the RSS fill that would
  give brand-new videos their date is planned, not built.
- `duration` can be `None` for a stream that has not finished.

## Try it (read-only, uses the network, writes nothing)
```bash
uv run python -c "
from seeker_sdk_core import DEFAULT_CHANNEL_URL
from seeker_sdk_videos import SourceConfig
from seeker_sdk_videos.sources.ytdlp import YtDlpSource
s = YtDlpSource(SourceConfig(strict=True))
cid = s.channel_id(DEFAULT_CHANNEL_URL)
print(cid, s.uploads_url(cid))
for v in s.fetch_recent(cid, limit=3): print(v['video_id'], repr(v['upload_date']), v['duration'], v['title'][:40])
"
```

To see the whole workflow instead, use the Tilt buttons or the `local:`/`act:` tasks described in
`AGENTS.md`.

## Mistakes we have made or can easily make
- **Listing from the `/videos` tab.** It missed 136 of 194 videos (all the live streams). Use the
  uploads playlist (PR #352).
- **Using a normal yt-dlp run on GitHub.** The channel-id lookup used to do this and failed with the bot
  check. Making it flat fixed it and cut a local run from about 4 minutes to 2 seconds (PR #348).
- **Expecting private or removed videos.** No source returns them, so a rebuild drops them.
- **Counting on RSS for history.** It only has 15 items. If the daily run is down for more than about 7
  weeks, a date-from-RSS plan would miss videos.
- **Copying the API's date handling to yt-dlp.** The API gives `publishedAt` (date and time, we cut it to
  the date). yt-dlp's flat listing gives nothing, so code must cope with `""`.
- **Putting a fallback inside a plugin.** Choose the method in `resolve_method` and fail loudly.

## If you add a source
Follow the "Write one" steps in primer 3. Return dicts from `seeker_sdk_core.new_video(...)`, honour
`strict`, say whether you `requires_api_key`, and write the test with a fake like the one in
`sdks/videos/tests/test_method_and_service.py`. The checks for the real sources are in
`sdks/videos/tests/test_sources_and_catalog.py`.
