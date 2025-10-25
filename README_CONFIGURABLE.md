# Configurable Video Fetching and Transcript Download System

This system provides fully configurable video fetching and transcript downloading with **NO automatic fallbacks**. You explicitly choose which methods to use, and if they fail, the system reports clear errors instead of silently falling back to other methods.

## Features

- **Configurable Master List Fetching**: Choose between YouTube Data API v3 or yt-dlp
- **Configurable Transcript Downloading**: Choose between yt-dlp or youtube-transcript-api
- **Optional Proxy Support**: Configure proxy settings for both methods
- **Optional Cookies Support**: Use browser cookies with yt-dlp
- **No Automatic Fallbacks**: Clear error reporting when configured methods fail
- **Transcript Management**: Download, link, and manage video transcripts

## Configuration

Edit `config.env` to configure the system:

```bash
# Master List Method (youtube_api or ytdlp)
MASTER_LIST_METHOD=youtube_api

# Transcript Method (ytdlp or youtube_transcript_api)
TRANSCRIPT_METHOD=ytdlp

# YouTube API Configuration
YOUTUBE_API_KEY=your_api_key_here

# File Paths
MASTER_FILE=data/videos_master.json
CHANNEL_URL=https://www.youtube.com/@AdamSeekerOfficial

# Update Settings
MAX_VIDEOS_PER_UPDATE=50
UPDATE_FREQUENCY=daily

# yt-dlp Configuration (optional)
YTDLP_COOKIES_FILE=./cookies.txt
YTDLP_USE_PROXY=false

# Proxy Configuration (optional)
WEBSHARE_PROXY=http://username:password@proxy.webshare.io:80

# Notification Settings
DISCORD_WEBHOOK_URL=your_discord_webhook_here
EMAIL_NOTIFICATIONS=false

# Categories (comma-separated)
DEFAULT_CATEGORIES=critique-of-islam,theology,apologetics,debate
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your settings in `config.env`

3. Validate your configuration:
```bash
python scripts/validate_config.py
```

## Usage

### 1. Update Master List

Update the master video list with new videos:

```bash
# Basic update
python scripts/update_master_configurable.py

# Update with transcript downloading
python scripts/update_master_configurable.py --download-transcripts

# Rebuild from scratch
python scripts/update_master_configurable.py --rebuild --download-transcripts
```

### 2. Rebuild Master List

Completely rebuild the master list from scratch:

```bash
# Basic rebuild
python scripts/rebuild_master_configurable.py

# Rebuild with transcript downloading
python scripts/rebuild_master_configurable.py --download-transcripts

# Rebuild without preserving manual data
python scripts/rebuild_master_configurable.py --no-preserve
```

### 3. Manage Transcripts

Download and manage video transcripts:

```bash
# Show transcript statistics
python scripts/manage_transcripts.py stats

# List videos without transcripts
python scripts/manage_transcripts.py list-missing

# Download missing transcripts
python scripts/manage_transcripts.py download-missing

# Download transcript for specific video
python scripts/manage_transcripts.py download VIDEO_ID VIDEO_URL

# Check if transcript is available
python scripts/manage_transcripts.py check VIDEO_ID VIDEO_URL
```

### 4. Validate Configuration

Test your configuration before running main scripts:

```bash
python scripts/validate_config.py
```

## Configuration Methods

### Master List Fetching

#### YouTube Data API v3 (`youtube_api`)
- **Requires**: `YOUTUBE_API_KEY`
- **Pros**: Official API, reliable, structured data
- **Cons**: Requires API key, has quotas
- **Configuration**: Set `MASTER_LIST_METHOD=youtube_api` and provide `YOUTUBE_API_KEY`

#### yt-dlp (`ytdlp`)
- **Requires**: None (but cookies and proxy are optional)
- **Pros**: No API key needed, can use cookies/proxy
- **Cons**: May be rate limited, less structured
- **Configuration**: Set `MASTER_LIST_METHOD=ytdlp`, optionally set `YTDLP_COOKIES_FILE` and `YTDLP_USE_PROXY`

### Transcript Downloading

#### yt-dlp (`ytdlp`)
- **Requires**: None (but cookies and proxy are optional)
- **Pros**: Can use cookies/proxy, supports multiple formats
- **Cons**: May be rate limited
- **Configuration**: Set `TRANSCRIPT_METHOD=ytdlp`, optionally set `YTDLP_COOKIES_FILE` and `YTDLP_USE_PROXY`

#### YouTube Transcript API (`youtube_transcript_api`)
- **Requires**: None (but proxy is optional)
- **Pros**: No cookies needed, simple API
- **Cons**: Limited to available transcripts
- **Configuration**: Set `TRANSCRIPT_METHOD=youtube_transcript_api`, optionally set `WEBSHARE_PROXY`

## Optional Configuration

### Cookies File
- **Purpose**: Use browser cookies with yt-dlp to avoid rate limiting
- **Format**: Netscape cookies.txt format
- **Configuration**: Set `YTDLP_COOKIES_FILE=./cookies.txt`
- **How to get**: Use browser extension to export cookies

### Proxy Support
- **Purpose**: Use proxy for requests to avoid rate limiting or access restrictions
- **Format**: `http://username:password@host:port`
- **Configuration**: Set `WEBSHARE_PROXY=http://username:password@proxy.webshare.io:80`
- **Usage**: Both yt-dlp methods can use proxy

## Error Handling

The system has **NO automatic fallbacks**. If your configured method fails:

1. **Clear Error Messages**: The system reports exactly what went wrong
2. **No Silent Failures**: You'll know immediately if something isn't working
3. **Configuration Validation**: Use `validate_config.py` to test before running
4. **Method-Specific Errors**: Different error messages for different failure types

## File Structure

```
/workspace/
├── config.env                          # Configuration file
├── data/
│   ├── videos_master.json             # Master video list
│   └── transcripts/                   # Downloaded transcripts
├── logs/                              # Log files
├── scripts/
│   ├── config_manager.py              # Configuration management
│   ├── video_fetchers.py              # Video fetching implementations
│   ├── transcript_downloaders.py      # Transcript downloading implementations
│   ├── update_master_configurable.py  # Configurable update script
│   ├── rebuild_master_configurable.py # Configurable rebuild script
│   ├── manage_transcripts.py          # Transcript management script
│   └── validate_config.py             # Configuration validation script
└── requirements.txt                   # Python dependencies
```

## Transcript Storage

- **Location**: `data/transcripts/`
- **Format**: VTT (WebVTT) with timestamps
- **Naming**: `{video_id}.vtt`
- **Linking**: Transcripts are linked to videos in `videos_master.json`

## Logging

All scripts log to both console and log files:
- **Update logs**: `logs/update_master.log`
- **Rebuild logs**: `logs/rebuild_master.log`
- **Transcript logs**: `logs/manage_transcripts.log`
- **Validation logs**: `logs/validate_config.log`

## Troubleshooting

### Common Issues

1. **"API key is required"**: Set `YOUTUBE_API_KEY` in `config.env`
2. **"No transcript available"**: Some videos don't have transcripts
3. **"Rate limited"**: Use cookies file or proxy with yt-dlp methods
4. **"Configuration validation failed"**: Check your `config.env` file

### Validation

Always run `python scripts/validate_config.py` before using the system to ensure your configuration is correct.

### Method Selection

- **For reliability**: Use YouTube Data API for master list fetching
- **For no API key**: Use yt-dlp for both fetching and transcripts
- **For transcripts only**: Use youtube-transcript-api (simpler, no cookies needed)
- **For rate limiting**: Use yt-dlp with cookies and proxy

## Migration from Old System

The old scripts (`update_master.py`, `rebuild_master.py`) are still available but use automatic fallbacks. The new configurable scripts (`*_configurable.py`) require explicit configuration but provide better control and error reporting.

To migrate:
1. Configure your preferred methods in `config.env`
2. Run `python scripts/validate_config.py` to test
3. Use the new `*_configurable.py` scripts instead of the old ones