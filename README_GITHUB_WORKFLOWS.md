# GitHub Workflows for Configurable Video System

This repository includes GitHub Actions workflows that allow you to configure and run the video fetching and transcript downloading system through the GitHub UI.

## Required GitHub Secrets

Before using the workflows, you need to set up the following secrets in your repository:

### Required Secrets

1. **YOUTUBE_API_KEY** - Your YouTube Data API v3 key (required for `youtube_api` method)
2. **WEBSHARE_PROXY_USERNAME** - Your Webshare proxy username
3. **WEBSHARE_PROXY_PASSWORD** - Your Webshare proxy password

### Optional Secrets

4. **DISCORD_WEBHOOK_URL** - Discord webhook for notifications (optional)

## How to Set Up Secrets

1. Go to your repository on GitHub
2. Click on **Settings** tab
3. Click on **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Add each secret with the appropriate value

## Available Workflows

### 1. Update Video List (`update-videos.yml`)

**Purpose**: Update the master video list with new videos and optionally download transcripts.

**Manual Inputs**:
- **Master list method**: Choose between `youtube_api` or `ytdlp`
- **Transcript method**: Choose between `ytdlp` or `youtube_transcript_api`
- **Enable Webshare proxy**: Boolean to enable/disable proxy
- **Enable cookies for yt-dlp**: Boolean to enable/disable cookies
- **Download transcripts**: Boolean to download transcripts for videos
- **Maximum videos**: Number of videos to process (default: 50)
- **Action type**: Choose between `update`, `rebuild`, `download_transcripts_only`, or `validate_config`

**Usage**:
1. Go to **Actions** tab in your repository
2. Select **Update Video List** workflow
3. Click **Run workflow**
4. Configure the inputs as needed
5. Click **Run workflow**

### 2. Download Transcripts (`download-transcripts.yml`)

**Purpose**: Download transcripts for existing videos in the master list.

**Manual Inputs**:
- **Transcript method**: Choose between `ytdlp` or `youtube_transcript_api`
- **Enable Webshare proxy**: Boolean to enable/disable proxy
- **Enable cookies for yt-dlp**: Boolean to enable/disable cookies
- **Maximum videos**: Number of videos to process (default: 50)
- **Specific video IDs**: Comma-separated list of video IDs to process (optional)

**Usage**:
1. Go to **Actions** tab in your repository
2. Select **Download Transcripts** workflow
3. Click **Run workflow**
4. Configure the inputs as needed
5. Click **Run workflow**

### 3. Validate Configuration (`validate-config.yml`)

**Purpose**: Test and validate your configuration without making changes.

**Manual Inputs**:
- **Master list method**: Choose between `youtube_api` or `ytdlp`
- **Transcript method**: Choose between `ytdlp` or `youtube_transcript_api`
- **Enable Webshare proxy**: Boolean to enable/disable proxy
- **Enable cookies for yt-dlp**: Boolean to enable/disable cookies

**Usage**:
1. Go to **Actions** tab in your repository
2. Select **Validate Configuration** workflow
3. Click **Run workflow**
4. Configure the inputs as needed
5. Click **Run workflow**

## Configuration Methods

### Master List Fetching

#### YouTube Data API v3 (`youtube_api`)
- **Requires**: `YOUTUBE_API_KEY` secret
- **Pros**: Official API, reliable, structured data
- **Cons**: Requires API key, has quotas
- **Best for**: Production use, reliable data

#### yt-dlp (`ytdlp`)
- **Requires**: None (but cookies and proxy are optional)
- **Pros**: No API key needed, can use cookies/proxy
- **Cons**: May be rate limited, less structured
- **Best for**: When you don't have API key, need cookies/proxy

### Transcript Downloading

#### yt-dlp (`ytdlp`)
- **Requires**: None (but cookies and proxy are optional)
- **Pros**: Can use cookies/proxy, supports multiple formats
- **Cons**: May be rate limited
- **Best for**: When you need cookies/proxy support

#### YouTube Transcript API (`youtube_transcript_api`)
- **Requires**: None (but proxy is optional)
- **Pros**: No cookies needed, simple API, supports Webshare proxy
- **Cons**: Limited to available transcripts
- **Best for**: Simple transcript downloading, when you have Webshare proxy

## Proxy Configuration

### Webshare Proxy Support

The workflows support Webshare proxy for both methods:

- **For youtube-transcript-api**: Uses `WebshareProxyConfig` with username/password
- **For yt-dlp**: Uses direct proxy URL format

### Setting Up Webshare Proxy

1. Get your Webshare proxy credentials
2. Add `WEBSHARE_PROXY_USERNAME` and `WEBSHARE_PROXY_PASSWORD` to GitHub secrets
3. Enable "Enable Webshare proxy" in workflow inputs

## Cookies Support

### yt-dlp Cookies

If you enable cookies for yt-dlp:

1. The workflow will create a `cookies.txt` file
2. You can add your browser cookies to this file
3. This helps avoid rate limiting and authentication issues

### Getting Cookies

1. Use a browser extension to export cookies
2. Save as `cookies.txt` in Netscape format
3. The workflow will use these cookies automatically

## Workflow Outputs

### Artifacts

Each workflow creates log artifacts that you can download:
- **Logs**: Detailed logs of the workflow execution
- **Transcripts**: Downloaded transcript files (if applicable)

### Git Commits

Successful workflows will automatically commit changes:
- Updated `data/videos_master.json`
- New transcript files in `data/transcripts/`
- Log files in `logs/`

## Troubleshooting

### Common Issues

1. **"API key is required"**: Make sure `YOUTUBE_API_KEY` secret is set
2. **"Proxy authentication failed"**: Check `WEBSHARE_PROXY_USERNAME` and `WEBSHARE_PROXY_PASSWORD` secrets
3. **"No transcript available"**: Some videos don't have transcripts
4. **"Rate limited"**: Try using cookies or proxy with yt-dlp methods

### Validation

Always run the **Validate Configuration** workflow first to test your setup before running other workflows.

### Logs

Check the workflow logs and downloaded artifacts for detailed error information.

## Example Workflows

### Basic Update (YouTube API + Transcript API)
1. Master list method: `youtube_api`
2. Transcript method: `youtube_transcript_api`
3. Enable Webshare proxy: `true`
4. Download transcripts: `true`

### Advanced Update (yt-dlp + Cookies)
1. Master list method: `ytdlp`
2. Transcript method: `ytdlp`
3. Enable cookies for yt-dlp: `true`
4. Enable Webshare proxy: `true`
5. Download transcripts: `true`

### Transcript Only
1. Use **Download Transcripts** workflow
2. Transcript method: `youtube_transcript_api`
3. Enable Webshare proxy: `true`
4. Maximum videos: `100`

## Security Notes

- Never commit API keys or proxy credentials to the repository
- Use GitHub secrets for all sensitive information
- The workflows automatically create configuration files with secrets
- All sensitive data is masked in workflow logs