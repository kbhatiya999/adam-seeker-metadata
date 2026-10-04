# Video details and transcripts: findings (tested 2026-10-04/05)

Status: **findings and a plan, not built yet** (except where marked "done").

## What the master list is missing
- `duration` is missing for all videos: the API path never saved it.
- Videos found through yt-dlp get an empty `upload_date`/`description` (flat listing has neither), so they sort last.

## Sources of details (all checked from a GitHub runner, no cookies)

| Source | Gives | Limits |
|---|---|---|
| yt-dlp flat `/videos` tab | id, title, duration (s), view count (rounded, e.g. 27000) | no date, no description |
| yt-dlp flat uploads playlist (`playlist?list=UU<channel id>`) | the same + `live_status` (e.g. `was_live`); includes live streams and shorts | no date, no description |
| RSS `feeds/videos.xml?channel_id=<id>` | published date, description, exact view count | **only the 15 newest videos** (about 7 weeks on this channel: ~9-10 uploads a month, max 2 in a day) |
| YouTube API `videos.list` (50 ids per call) | everything incl. date, duration, statistics | needs `YOUTUBE_API_KEY` |
| yt-dlp per video | everything | **blocked from cloud IPs** ("Sign in to confirm you're not a bot"), fine from a home IP |

"Flat" = `extract_flat`: yt-dlp reads only the list page and does not open each video. Cloud IPs are blocked on the per-video request but not on list pages. Done: the channel-ID lookup uses flat (PR #348), which fixed `MASTER_LIST_METHOD=ytdlp` on GitHub and cut the local run from ~4 min to 2 s.

## Plan (not built)
1. yt-dlp path: list the uploads playlist (duration, views, live status); fill upload date and description from RSS.
2. API path: also save duration and view count (`videos.list`, 1 unit per 50 videos).
3. `local:videos:backfill`: add `duration` / live flag to existing videos from the flat listing.
4. Warn in the log how many videos still lack an upload date (the RSS 15-video window can be outrun if the daily run is down for ~7 weeks); use the API as backstop when a key is present, or backfill from a home IP.

## Rebuild
- Today: the whole list is replaced from a fresh fetch; only `categories`, `relevance_score`, `notes`, `key_topics` and `transcript_file` are copied back. Private/removed videos are dropped (a rebuild dropped 10 private videos on 2026-10-04; left out on purpose).
- With the API: complete (dates, descriptions, and the new duration/view count).
- With yt-dlp: flat gives duration/views/live status for all, but dates/descriptions only for the 15 newest (RSS). So a rebuild must **merge**: keep an existing video's `upload_date` and `description`, refresh duration and view count, and log the videos still without a date. A yt-dlp rebuild already empties every `upload_date` today (existing flaw).

## Transcripts (`scripts/transcripts.py`, explicit method, no fallback)

| Where | `youtube_transcript_api` | `ytdlp` |
|---|---|---|
| local (home IP) | works (e.g. 0.7 MB for a 1-hour video) | works after the single-language fix (PR #347; ~3 MB, repeats rolling lines) |
| act (Docker on the same machine) | same IP as local; no act task runs transcripts | same |
| GitHub Actions | **fails**: YouTube blocks the runner's IP | **fails**: "Sign in to confirm you're not a bot" |

- yt-dlp 429 was caused by asking for several/translated tracks, not by missing cookies; it now picks ONE track (manual English, else manual any, else automatic original `xx-orig`, else automatic English; `live_chat` is ignored).
- A video with no captions yet (e.g. a live stream from the last day or two) correctly fails with both methods.
- To make transcripts work on GitHub you need a proxy (`PROXY_URL` / `WEBSHARE_PROXY_USERNAME`+`WEBSHARE_PROXY_PASSWORD`) or cookies. Cookies tied to a Google account risk the account being flagged and expire (rotate while the browser is open; nominally 1-2 years). Planned: `YTDLP_COOKIES_B64` for local/act/gh; no transcripts workflow exists yet.
- Transcript files (`data/transcripts/`) are git-ignored: they are large.

- Compared on a 4.7-hour video (2026-10-05): both methods produced byte-identical plain text (42,703 words); they differ only in the VTT (yt-dlp 2.8 MB with rolling duplicate cues, youtube-transcript-api 0.66 MB). `mise run local:transcripts:compare -- VIDEO_ID` (PR #350) reproduces this.
