# seeker-sdk-transcripts

Downloads video transcripts. The method is explicit and has no fallback.

- **Methods are plugins** (entry-point group `seeker.transcript_methods`): `ytdlp` and
  `youtube_transcript_api`. Both download the same source format (default `ttml`).
- **Two format choices**: `source_format` (what is downloaded: ttml, srv1, srt, vtt) and `finals`
  (what you keep: any of srt, vtt, txt). A post-processor converts the download into the finals
  (for yt-dlp a real yt-dlp post-processor; no ffmpeg needed).
- One caption track per video (the video's own language), which avoids YouTube's HTTP 429.
- `compare()` runs several methods side by side and diffs the final files.

```python
from seeker_sdk_transcripts import TranscriptConfig, get_method

cfg = TranscriptConfig(finals=("srt", "txt"))
method = get_method("ytdlp", cfg)
path = method.download("dQw4w9WgXcQ", "data/transcripts")   # -> data/transcripts/dQw4w9WgXcQ.srt
```

Note: YouTube blocks both methods from cloud IPs (GitHub Actions) without a proxy or cookies.
