# 🎥 Automated Video List Maintenance

This system automatically maintains your master video list by discovering new videos from Adam Seeker's YouTube channel and providing tools for manual categorization and management.

## 🚀 Quick Start

1. **Setup the automation system:**
   ```bash
   python scripts/setup_automation.py
   ```

2. **Get a YouTube API key:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable YouTube Data API v3
   - Create credentials (API Key)
   - Copy the API key

3. **Configure the system:**
   ```bash
   # Set environment variable
   export YOUTUBE_API_KEY="your_api_key_here"
   
   # Or edit config.env file
   nano config.env
   ```

4. **Test the update script:**
   ```bash
   python scripts/update_master.py
   ```

## 📁 File Structure

```
├── data/
│   └── videos_master.json          # Master video list
├── scripts/
│   ├── update_master.py            # Automated video discovery
│   ├── manage_videos.py            # Manual management tools
│   └── setup_automation.py         # Initial setup script
├── logs/
│   └── update_master.log           # Update logs
├── .github/workflows/
│   └── update-videos.yml           # GitHub Actions workflow
├── requirements.txt                # Python dependencies
└── config.env                      # Configuration file
```

## 🔧 Scripts Overview

### `update_master.py`
**Automated video discovery and list updates**

```bash
# Run update (uses API key if available, falls back to yt-dlp)
python scripts/update_master.py

# With specific API key
YOUTUBE_API_KEY="your_key" python scripts/update_master.py
```

**Features:**
- Fetches new videos from YouTube channel
- Compares with existing videos to avoid duplicates
- Adds new videos with status "uncategorized"
- Creates automatic backups
- Comprehensive logging

### `manage_videos.py`
**Manual video management and categorization**

```bash
# List uncategorized videos
python scripts/manage_videos.py list-uncategorized

# Generate comprehensive report
python scripts/manage_videos.py report

# Interactive categorization mode
python scripts/manage_videos.py interactive

# Categorize specific video
python scripts/manage_videos.py categorize VIDEO_ID --categories "islam,critique" --relevance 8 --notes "Important debate"

# Mark video as priority
python scripts/manage_videos.py priority VIDEO_ID --category "urgent" --relevance 10
```

**Features:**
- Interactive video categorization
- Relevance scoring (1-10)
- Category management
- Comprehensive reporting
- Priority video handling

### `setup_automation.py`
**Initial setup and validation**

```bash
python scripts/setup_automation.py
```

**Features:**
- Updates existing master list structure
- Validates all required files
- Creates sample configuration
- Provides setup instructions

## 🤖 GitHub Actions Automation

The system includes a GitHub Actions workflow that runs automatically:

- **Schedule:** Daily at 6 AM UTC
- **Manual trigger:** Available via GitHub UI
- **Auto-commit:** Commits new videos to repository
- **Notifications:** Creates GitHub issues for new videos
- **Logs:** Uploads detailed logs as artifacts

### Setup GitHub Actions

1. **Add API key secret:**
   - Go to repository Settings
   - Navigate to Secrets and Variables > Actions
   - Click "New repository secret"
   - Name: `YOUTUBE_API_KEY`
   - Value: Your YouTube API key

2. **Enable workflow:**
   - Go to Actions tab
   - Find "Update Video List" workflow
   - Click "Enable workflow"

3. **Test manually:**
   - Go to Actions tab
   - Select "Update Video List"
   - Click "Run workflow"

## 📊 Master List Structure

The master list now includes automation fields:

```json
{
  "videos": [
    {
      "video_id": "abc123",
      "title": "Video Title",
      "url": "https://www.youtube.com/watch?v=abc123",
      "upload_date": "2024-01-01",
      "duration": "15:30",
      "description": "Video description",
      "transcript_file": "transcripts/abc123.txt",
      "categories": ["critique-of-islam"],
      "relevance_score": 9,
      "key_topics": ["topic1", "topic2"],
      "notes": "Why this video is relevant",
      
      // Automation fields
      "status": "categorized|uncategorized|archived",
      "auto_detected": true,
      "needs_review": false,
      "last_checked": "2024-01-01"
    }
  ],
  "last_updated": "2024-01-01",
  "total_videos": 1,
  "channel_url": "https://www.youtube.com/@AdamSeekerOfficial"
}
```

## 🔄 Workflow Process

### Daily Automated Process
1. **Discovery:** Script fetches latest videos from YouTube
2. **Comparison:** Identifies new videos not in master list
3. **Addition:** Adds new videos with status "uncategorized"
4. **Notification:** Creates GitHub issue for manual review
5. **Commit:** Automatically commits changes to repository

### Weekly Manual Review
1. **Review:** Check GitHub issues for new videos
2. **Categorize:** Use management script to assign categories
3. **Score:** Set relevance scores (1-10)
4. **Notes:** Add detailed notes about usefulness
5. **Update:** Change status from "uncategorized" to "categorized"

## 🛠️ Configuration Options

Edit `config.env` to customize:

```bash
# YouTube API Configuration
YOUTUBE_API_KEY=your_api_key_here

# File Paths
MASTER_FILE=data/videos_master.json
CHANNEL_URL=https://www.youtube.com/@AdamSeekerOfficial

# Update Settings
MAX_VIDEOS_PER_UPDATE=50
UPDATE_FREQUENCY=daily

# Notification Settings
DISCORD_WEBHOOK_URL=your_discord_webhook_here
EMAIL_NOTIFICATIONS=false

# Categories
DEFAULT_CATEGORIES=critique-of-islam,theology,apologetics,debate
```

## 📈 Monitoring and Reports

### View Update Logs
```bash
# Check recent updates
tail -f logs/update_master.log

# View all logs
cat logs/update_master.log
```

### Generate Reports
```bash
# Comprehensive report
python scripts/manage_videos.py report

# List uncategorized videos
python scripts/manage_videos.py list-uncategorized
```

### GitHub Actions Logs
- Go to Actions tab in GitHub
- Click on latest workflow run
- View detailed logs and artifacts

## 🔧 Troubleshooting

### Common Issues

**1. API Key Issues**
```bash
# Test API key
curl "https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&key=YOUR_API_KEY"
```

**2. yt-dlp Fallback**
- If API fails, system automatically uses yt-dlp
- No additional configuration needed
- May be slower but more reliable

**3. Permission Issues**
```bash
# Make scripts executable
chmod +x scripts/*.py

# Check file permissions
ls -la scripts/
```

**4. Missing Dependencies**
```bash
# Install requirements
pip install -r requirements.txt

# Or install individually
pip install yt-dlp requests python-dateutil
```

### Debug Mode
```bash
# Run with verbose logging
python scripts/update_master.py 2>&1 | tee debug.log
```

## 🚀 Advanced Features

### Priority Videos
Mark important videos for immediate attention:
```bash
python scripts/manage_videos.py priority VIDEO_ID --category "urgent" --relevance 10
```

### Batch Operations
Process multiple videos at once:
```bash
# Interactive mode for batch categorization
python scripts/manage_videos.py interactive
```

### Custom Categories
Add your own categories in the management script or config file.

## 📝 Best Practices

1. **Regular Review:** Check GitHub issues weekly for new videos
2. **Consistent Scoring:** Use 1-10 scale consistently
3. **Detailed Notes:** Add meaningful notes for future reference
4. **Backup Strategy:** System creates automatic backups
5. **API Limits:** YouTube API has daily limits (10,000 requests)
6. **Version Control:** All changes are tracked in Git

## 🤝 Contributing

To improve the automation system:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This automation system is part of your video management project. Use and modify as needed for your specific requirements.

---

**Need Help?** Check the logs, run the setup script, or review the GitHub Actions workflow for detailed error information.
