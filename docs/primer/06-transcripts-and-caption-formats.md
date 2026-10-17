# Primer 6: Transcripts and caption formats

**You need:** nothing special. **Read after:** [03-plugins-and-entry-points.md](03-plugins-and-entry-points.md) and [04-the-master-list.md](04-the-master-list.md).
**Code:** `sdks/transcripts/src/seeker_sdk_transcripts/`. **Findings with dates and numbers:** [../video-details-and-transcripts.md](../video-details-and-transcripts.md).

## What a caption file is
A list of **cues**. Each cue is a start time, an end time and some text. The same information comes in
several file formats:

| Format | Looks like | Notes |
|---|---|---|
| `ttml` | XML, `<p begin="0.5s" end="2.0s">text</p>` | compact, one cue per sentence. **Our default download.** |
| `srv1` | XML, `<text start="0.5" dur="1.5">text</text>` | compact |
| `srt` | numbered blocks, `00:00:00,500 --> 00:00:02,000` | the usual "subtitle file" |
| `vtt` | `WEBVTT`, same as srt with dots | YouTube's own automatic `vtt` is a "rolling caption" file: every cue repeats the previous line, so it is about 4 times bigger |

In code a cue is `Cue = (start_seconds, end_seconds, text)` (`formats.py`).

## Two kinds of format: what we download and what we keep
This is the idea people mix up most.

- **Source format** (`--format`, `TranscriptConfig.source_format`): what is downloaded from YouTube.
  One of `ttml` (default), `srv1`, `srt`, `vtt`.
- **Final formats** (`--final`, `TranscriptConfig.finals`): the files you end up with. A comma list from
  `srt`, `vtt`, `txt`. The default is `srt,txt`.

A conversion step turns the source into the finals: `parse_cues` reads any source format (and merges
neighbouring identical cues), `render` writes `srt`, `vtt` or `txt`. `produce_finals` does both and
deletes the downloaded file unless `keep_source` is set. Files are named `<video_id>.<format>` in
`data/transcripts/` (git-ignored, because they are large).

The master list gets two links: `transcript_file` (the first of srt, vtt, txt that exists, called the
primary file) and `transcript_text_file` (the txt).

## The two methods
Both are plugins (`seeker.transcript_methods`) and both download the **same source format**, so they
can be compared fairly.

**`ytdlp`** (`methods/ytdlp.py`)
1. Ask yt-dlp which captions the video has (`check` stops here).
2. `pick_language` chooses **one** caption track: a manual track (English if there is one), else the
   automatic original (`xx-orig`), else automatic English, else the first. `live_chat` is a chat replay,
   not captions, so it is ignored.
3. Download only that track. A yt-dlp **post-processor** (`TextPostProcessor`, registered at
   `before_dl`, which runs even with `skip_download`) converts the file into the finals. We wrote our own
   because yt-dlp's built-in subtitle converter needs ffmpeg and cannot write `txt`.
4. yt-dlp names files `<id>.<language>.<ext>`. We rename them to `<id>.<ext>`.

**`youtube_transcript_api`** (`methods/library.py`)
1. List the video's transcripts, choose one by `config.languages`, else the first.
2. The library normally returns parsed text only. We take the transcript's own URL and request it again
   with `&fmt=<source format>` through the library's proxy-aware session, so we get the raw file.
3. Convert with `produce_finals`, exactly as above.
4. It uses the library's private `_url` and `_http_client`. The code checks they exist and raises a clear
   error if a new library version removed them. **Re-check this when upgrading the library.**

Result: both methods produce **byte-identical** `srt`, `vtt` and `txt` (tested on 4 videos on
2026-10-05, and the plain text of a 4.7-hour video matched at 42,703 words).

## Rules of the SDK
- **No fallback.** The method you choose is the only one run. If it fails, you get a `TranscriptError`.
- **`None` means no captions**, which is different from an error. A live stream from the last day or two
  usually has none yet, and both methods correctly report that.
- `download_many` (`service.py`) logs and counts failures and carries on. It saves the master list after
  every success, so an interrupted run loses nothing.
- `compare` runs each method into `data/transcripts/compare/<id>/<method>/`, never touches the master
  list, and `diff_outcomes` compares the final files.

## Where it works
| | `youtube_transcript_api` | `ytdlp` |
|---|---|---|
| local (home IP) | works | works |
| GitHub Actions | **fails**, YouTube blocks the runner's IP | **fails**, "Sign in to confirm you're not a bot" |

Getting past that needs a proxy or cookies, which are both fields of `Network` in `config.py`. No
workflow downloads transcripts yet. Cookies are tied to a Google account (risk of the account being
flagged, and they expire), so that is a decision for later; see the findings doc.

## Try it
Offline, nothing downloaded: turn a small ttml into srt and txt.

```bash
uv run python -c "
import os, tempfile
from seeker_sdk_transcripts import parse_cues, render
ttml = '<tt xmlns=\"http://www.w3.org/ns/ttml\"><body><div><p begin=\"0.5s\" end=\"2s\">Hello</p><p begin=\"2s\" end=\"3s\">Hello</p><p begin=\"3s\" end=\"5s\">world</p></div></body></tt>'
path = os.path.join(tempfile.mkdtemp(), 'x.ttml'); open(path, 'w').write(ttml)
cues = parse_cues(path)
print(cues); print(render(cues, 'srt')); print(render(cues, 'txt'))
"
```

Notice that the two `Hello` cues became one. With the network (writes only under the git-ignored
`data/transcripts/compare/`):

```bash
mise run local:transcripts:compare -- VIDEO_ID
```

## Mistakes we have made or can easily make
- **HTTP 429 from YouTube.** We asked yt-dlp for several languages (`en.*`). Machine-translated tracks,
  such as English on a Hindi video, are limited the hardest. The fix was `pick_language`: one track.
- **Treating `live_chat` as captions.** It is the chat replay of a stream.
- **Downloading `vtt` and calling it small.** YouTube's `vtt` repeats lines. Download `ttml` and render
  `vtt` yourself.
- **Adding a final format in only one place.** A new one needs `FINAL_FORMATS` in `config.py`, a branch
  in `render`, and a test. Then run `compare` to prove both methods still agree.
- **Relying on the library's private attributes without the guard.** Keep the `hasattr` check.
- **Expecting transcripts from CI.** They fail there today for both methods. Do not build a workflow on
  them without a proxy or cookies plan.

## If you add a method
Follow the "Write one" steps in primer 3 with `--plugin transcript_methods`. Download in
`self.config.source_format`, finish with `produce_finals(...)` and return `primary_path(...)`. Tests for
the formats and the service are in `sdks/transcripts/tests/test_formats.py` and
`sdks/transcripts/tests/test_service.py`.
