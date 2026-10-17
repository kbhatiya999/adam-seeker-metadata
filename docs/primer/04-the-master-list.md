# Primer 4: The master list

**You need:** basic JSON and Python dicts. **Read after:** [03-plugins-and-entry-points.md](03-plugins-and-entry-points.md) is helpful but not required.
**Code:** `sdks/core/src/seeker_sdk_core/masterlist.py`. **Data:** `data/videos_master.json`.

## What it is
One JSON file with every video of the channel, kept in git. The daily workflow adds new videos to it,
people add categories and notes to it, and transcripts are linked from it. `MasterList` is the class
that reads and writes it, so no other code touches the file directly.

```json
{
  "videos": [ ... ],
  "last_updated": "2026-10-11",
  "total_videos": 196,
  "channel_url": "https://www.youtube.com/@AdamSeekerOfficial"
}
```

A rebuild also writes `rebuild_date` and `rebuild_reason`.

## One video
`new_video(...)` creates it, and the key order below is fixed on purpose (a different order would show
up as noise in every git diff):

```json
{
  "video_id": "do4vu3zEKVY",
  "title": "...",
  "url": "https://www.youtube.com/watch?v=do4vu3zEKVY",
  "upload_date": "2026-10-10",
  "duration": 18551,
  "description": "first 500 characters",
  "status": "uncategorized",
  "auto_detected": true,
  "needs_review": true,
  "last_checked": "2026-10-13"
}
```

- `upload_date` is `YYYY-MM-DD`. It is an empty string when the source cannot say (see
  [05-youtube-sources.md](05-youtube-sources.md)).
- `duration` (seconds) is only written by the yt-dlp source. It can be `null` for a stream that has not
  finished.
- Added later by people or tools: `categories`, `relevance_score`, `notes`, `key_topics`
  (`seeker videos manage ...`), and `transcript_file`, `transcript_text_file`, `transcript_downloaded`,
  `transcript_download_date` (set by `MasterList.link_transcript`). When a video has **no transcript**
  (a finished live stream, say) the transcript download writes `transcript_status: "unavailable"`,
  `transcript_attempts`, `transcript_checked` and `transcript_retry_after`, so it is not retried every run
  (see [06-transcripts-and-caption-formats.md](06-transcripts-and-caption-formats.md)). Finding the
  transcript later removes those four fields.

## The rules the file follows
1. **Newest first.** Sorted by `upload_date`, descending. Videos with no date go last.
2. **Same format always.** `indent=2`, `ensure_ascii=False` (Hindi/Urdu titles stay readable).
3. **Every save path sorts.** `save()` sorts. `write()` sorts unless you pass `sort=False` because the
   data is already sorted. If you add a new way to write, sort there too.
4. **Nobody deletes by accident.** `save()` moves the old file to `<file>.backup` first and puts it
   back if writing fails. Only the previous version is kept, because the next save replaces the backup.

## Who changes what

| Action | What happens | Writes with |
|---|---|---|
| `update` (daily) | fetches the 50 newest, **adds only** the ones whose id is not in the list yet. Existing videos are never changed. | `add()` then `save()` |
| `rebuild` | fetches everything and **replaces the list**, copying manual work back with `merge_manual`. The CLI makes a timestamped backup first (`apps/cli/src/seeker_cli/videos.py`). | `write(sort=False)` after sorting |
| `manage categorize / priority` | edits fields on one video (the catalog functions change it in memory, the CLI saves) | `write(sort=False)`, so no `.backup` |
| `transcripts download` | `link_transcript(...)` after each success | `write(sort=False)` |

## What a rebuild keeps (`merge_manual`)
For every freshly fetched video that also existed before:

- `upload_date` and `description` come from the old record **only if the new value is empty**
  (`FILL_IF_EMPTY`). This is what stops a yt-dlp rebuild from blanking every date.
- If the old record has `categories`, they are copied, and the video becomes `categorized` with
  `needs_review: false`.
- These fields are copied when set (`PRESERVED_FIELDS`): `relevance_score`, `notes`, `key_topics`,
  `transcript_file`, `transcript_text_file`, `transcript_downloaded`, `transcript_download_date` and the four
  transcript status fields.

Everything else comes from the fresh fetch. A video that the source does not return is **gone**.

## Loading: forgiving or strict
- `MasterList.load(path)` returns an **empty list** (and logs an error) when the file is missing or not
  valid JSON. `update` uses this.
- `MasterList.load_strict(path)` raises `SeekerError`. The `manage` and `transcripts` commands use it.
- `MasterList.existing_videos(path)` returns the old videos or `[]`, for rebuilds.

Use `load_strict` whenever silently starting from an empty list would be worse than stopping.

## Try it (read-only)
```bash
uv run seeker videos manage report
```

```bash
uv run python -c "from seeker_sdk_core import MasterList; m = MasterList.load_strict('data/videos_master.json'); print(len(m.videos), 'videos,', sum(1 for v in m.videos if not v.get('upload_date')), 'without a date')"
```

The Tilt `videos-report` resource shows the report and refreshes when the file changes.

## Mistakes we have made or can easily make
- **A rebuild dropped 10 private videos (2026-10-04).** A rebuild asks YouTube for what is public today.
  It was triggered by accident, because a workflow had a `push:` trigger. Rebuilds are manual only now.
- **A field that a rebuild forgets.** A rebuild only keeps what is in `PRESERVED_FIELDS`. It once lost
  `transcript_downloaded` and `transcript_download_date` for that reason. If you add a field that people or
  tools set later, add it to `PRESERVED_FIELDS` and to the test in `sdks/core/tests/test_masterlist.py`.
- **`last_updated` changes on every `add()`.** The workflow must not treat that as news. It counts added
  `"video_id"` lines in the diff instead.
- **Changing the key order or JSON format.** That rewrites the whole file in git. Keep both.
- **Reading the file with plain `json.load` somewhere new.** Go through `MasterList` so the rules above
  stay in one place.
