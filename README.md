# adam-seeker-metadata
Metadata repository for YouTube channel https://www.youtube.com/@AdamSeekerOfficial

## Downloading Transcripts with yt-dlp

This repository contains metadata and transcripts for the AdamSeekerOfficial YouTube channel. You can download transcripts using the `yt-dlp` command-line tool.

### Prerequisites

Install yt-dlp if you haven't already:
```bash
pip install yt-dlp
```

### Download Transcripts

To download transcripts from all videos in the AdamSeekerOfficial channel:

```bash
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download "https://www.youtube.com/@AdamSeekerOfficial/videos"
```

To download transcripts from live streams only:

```bash
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download "https://www.youtube.com/@AdamSeekerOfficial/streams"
```

### Command Options Explained

- `--write-subs`: Download subtitles if available
- `--write-auto-subs`: Download auto-generated subtitles
- `--sub-langs en`: Specify language (English)
- `--skip-download`: Skip downloading video files, only download transcripts
- `--output "%(uploader)s/%(upload_date)s_%(title)s.%(ext)s"`: Optional: Customize output filename format

### Download Specific Video Transcripts

To download transcripts from a specific video, replace the channel URL with the video URL:

```bash
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download "VIDEO_URL"
```
