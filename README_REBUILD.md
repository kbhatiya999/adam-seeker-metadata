# Rebuilding the video list

A **rebuild** fetches every video on the channel again and writes a fresh `data/videos_master.json`. It **keeps your manual work**: categories, scores, notes and transcript links.

The daily **update** only adds new videos. Use a rebuild only when the list itself needs repair.

| | Update | Rebuild |
|---|---|---|
| Fetches | new videos only | every video |
| Runs | daily, by itself | only when you start it |
| YouTube API use | low | higher (about one request per 50 videos) |
| Use it for | daily upkeep | fixing titles, dates or descriptions, recovering a broken file, after a format change |

## How to run it

Run these in this order. Each step is safer than the next.

**1. On your computer.** No question is asked, and a backup is always made:
```bash
mise run local:videos:rebuild
```

**2. The real workflow, in Docker.** It never commits:
```bash
mise run act:videos:rebuild
```

**3. On GitHub.** This commits to the branch and opens a summary issue. Either:
- go to **Actions → Rebuild Video List → Run workflow**, or
- run:
  ```bash
  mise run gh:videos:rebuild
  ```
  It uses your current branch, or `REF=main`.

Options go after `--`. For a completely fresh list, without your manual work:
```bash
mise run local:videos:rebuild -- --no-preserve
```

The other options are `--master-file FILE` and `--channel-url URL`.

## What is kept and what is refreshed

**Kept from the old list:**
- **Your categories.** The video stays `categorized`, with `needs_review: false`.
- **Your work on each video:** `relevance_score`, `notes`, `key_topics`.
- **Transcript links:** `transcript_file`, `transcript_text_file`, `transcript_downloaded`, `transcript_download_date`.
- **"No transcript yet" notes:** `transcript_status`, `transcript_attempts`, `transcript_checked`, `transcript_retry_after`.
- **`upload_date` and `description`,** whenever the new source has none. yt-dlp's fast listing has neither, so a rebuild never blanks them.

**Refreshed from YouTube:**
- `title`, `url`, `upload_date`, `description`
- `last_checked`, which is set to today

## Safety

- **Backups.** Before anything changes, the old list is copied to `data/videos_master.json.backup_YYYYMMDD_HHMMSS`. Every save also keeps `data/videos_master.json.backup`.
- **Sorting.** The new list is sorted newest first, as always.
- **No silent fallback.** The method follows `MASTER_LIST_METHOD`, so if the chosen method fails, the rebuild fails and the old list stays. With the setting unset, it uses the API if a key is present, and yt-dlp otherwise.

### Going back to a backup

List the backups:
```bash
ls data/videos_master.json.backup_*
```

Copy one back (use the date of yours):
```bash
cp data/videos_master.json.backup_20261004_034225 data/videos_master.json
```

Check the result:
```bash
mise run local:videos:manage report
```

Each step on GitHub is also a commit, so `git revert` undoes a rebuild there.

## What a rebuild prints

```
INFO - 🔑 YouTube API key provided
INFO - 📦 Created backup: data/videos_master.json.backup_20261004_034225
INFO - 🚀 Starting COMPLETE master list rebuild...
INFO - ✅ Found channel ID via API: UCLXC98YXDDPoaVEQsWPg4ow
INFO - 🔑 Fetching ALL videos using YouTube Data API v3
INFO - 📄 Fetching page 1...
INFO - ✅ Successfully fetched 194 videos from YouTube Data API
INFO - 🔄 Preserving manual categorizations from old videos...
INFO - ✅ Successfully rebuilt master list with 194 videos
INFO - 🎉 Rebuild completed successfully!
```

The full log is in `logs/rebuild_master.log`. On GitHub, it is in the run's logs and its summary issue.

## When something goes wrong

| Problem | What to do |
|---|---|
| YouTube API quota used up | Rebuild with yt-dlp for this one run: `FNOX_PROFILE=ytdlp mise run local:videos:rebuild`. The quota resets daily. |
| `youtube_api` chosen but no key | Add one with `mise run local:apikey:setup`, or switch to yt-dlp with `mise run local:profile:use -- ytdlp`. |
| Your categories are gone | Check you did not use `--no-preserve`, then copy a backup back (above). |
| The workflow fails at "Create rebuild summary issue" | Issues are off. Turn them on: **Settings → General → Features → Issues**. |

More problems and fixes are in [README.md](README.md#when-something-goes-wrong).
