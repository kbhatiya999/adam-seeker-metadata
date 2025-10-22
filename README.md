# adam-seeker-metadata
Metadata repository for YouTube channel https://www.youtube.com/@AdamSeekerOfficial

## Downloading Transcripts with yt-dlp

This repository contains metadata and transcripts for the AdamSeekerOfficial YouTube channel. You can download transcripts using the `yt-dlp` command-line tool.

### Prerequisites

Install yt-dlp using uv (recommended) or pip:
```bash
# Using uv (recommended)
uv add yt-dlp

# Or using pip
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

### Bulk Download from Links File

To download transcripts from multiple videos using a list of URLs, create a text file with one URL per line:

```bash
# Create a file with video URLs
echo "https://www.youtube.com/watch?v=VIDEO_ID_1" > video_links.txt
echo "https://www.youtube.com/watch?v=VIDEO_ID_2" >> video_links.txt
echo "https://www.youtube.com/watch?v=VIDEO_ID_3" >> video_links.txt

# Download transcripts from all URLs in the file
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download --batch-file video_links.txt
```

### Advanced Bulk Download Options

For more control over bulk downloads:

```bash
# Download with custom output directory and filename format
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download \
  --output "transcripts/%(uploader)s/%(upload_date)s_%(title)s.%(ext)s" \
  --batch-file video_links.txt

# Download with progress tracking and error handling
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download \
  --batch-file video_links.txt \
  --ignore-errors \
  --no-warnings
```
