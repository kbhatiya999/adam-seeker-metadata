# 🔄 Master List Rebuild System

This system provides comprehensive tools to rebuild your master video list from scratch when needed.

## 🎯 **Use Cases**

### 1. **Metadata Refresh**
- Update all video titles, descriptions, and upload dates
- Fix outdated or incorrect information
- Ensure consistency with current YouTube data

### 2. **Data Recovery**
- Fix corrupted master list files
- Recover from accidental data loss
- Restore from a clean state

### 3. **Fresh Start**
- Start over with clean, organized data
- Remove accumulated errors or inconsistencies
- Implement new data structure changes

## 🛠️ **Available Methods**

### **Method 1: Command Line (Local)**
```bash
# Basic rebuild (with confirmation)
python3 scripts/update_master.py --rebuild

# Force rebuild (no confirmation)
python3 scripts/update_master.py --rebuild --force

# Direct rebuild script
python3 scripts/rebuild_master.py --force
```

### **Method 2: GitHub Actions (Remote)**
1. Go to your repository's **Actions** tab
2. Find **"Rebuild Video List"** workflow
3. Click **"Run workflow"**
4. Select branch and click **"Run workflow"**

## 🔧 **Command Options**

### **Update Script with Rebuild Flag**
```bash
python3 scripts/update_master.py [OPTIONS]

Options:
  --rebuild              Completely rebuild the master list from scratch
  --master-file FILE     Path to master video list file
  --channel-url URL      YouTube channel URL
  --force                Skip confirmation prompts
```

### **Dedicated Rebuild Script**
```bash
python3 scripts/rebuild_master.py [OPTIONS]

Options:
  --master-file FILE     Path to master video list file
  --channel-url URL      YouTube channel URL
  --no-preserve          Do not preserve manual categorizations
  --force                Skip confirmation prompt
```

## 🛡️ **Safety Features**

### **Automatic Backup**
- Creates timestamped backup before rebuild
- Format: `videos_master.json.backup_YYYYMMDD_HHMMSS`
- Easy to restore if needed

### **Data Preservation**
- **Preserves manual categorizations** (categories, relevance scores, notes)
- **Preserves key topics** and transcript file references
- **Maintains manual status** (categorized vs uncategorized)

### **Confirmation Prompts**
- Clear warnings about data replacement
- Detailed explanation of what will happen
- Option to cancel before proceeding

## 📊 **Rebuild Process**

### **Step 1: Backup Creation**
```
📦 Created backup: data/videos_master.json.backup_20251022_194812
```

### **Step 2: Channel Discovery**
```
🔑 Using YouTube Data API to get channel ID
✅ Found channel ID via API: UCLXC98YXDDPoaVEQsWPg4ow
```

### **Step 3: Complete Video Fetch**
```
🔑 Fetching ALL videos using YouTube Data API v3
📄 Fetching page 1...
📄 No more pages available
✅ Successfully fetched 41 videos from YouTube Data API
```

### **Step 4: Data Preservation**
```
🔄 Preserving manual categorizations from old videos...
✅ Preserved manual data for X videos
```

### **Step 5: Master List Creation**
```
✅ Successfully rebuilt master list with 41 videos
🎉 Rebuild completed successfully!
```

## 🔍 **What Gets Preserved**

### **✅ Preserved Fields**
- `categories` - Manual category assignments
- `relevance_score` - Manual relevance scores (1-10)
- `notes` - Manual notes and comments
- `key_topics` - Manual topic assignments
- `transcript_file` - Transcript file references
- `status` - Categorized vs uncategorized status

### **🔄 Refreshed Fields**
- `title` - Video title from YouTube
- `description` - Video description from YouTube
- `upload_date` - Upload date from YouTube
- `url` - Video URL
- `last_checked` - Current timestamp
- `auto_detected` - Set to true for all videos

## 📈 **Rebuild vs Update**

| Feature | Update | Rebuild |
|---------|--------|---------|
| **Scope** | New videos only | All videos |
| **Speed** | Fast | Slower |
| **API Usage** | Low | High |
| **Data Loss Risk** | None | Low (with preservation) |
| **Use Case** | Daily maintenance | Recovery/refresh |

## 🚨 **Important Considerations**

### **API Limits**
- Rebuild uses more API quota than regular updates
- YouTube API has daily limits (10,000 requests)
- Rebuild may use 50-100 requests depending on video count

### **Data Loss Prevention**
- Always creates backup before rebuild
- Preserves manual categorizations by default
- Use `--no-preserve` only if you want a completely fresh start

### **Recovery Process**
If something goes wrong:
1. Find the backup file: `data/videos_master.json.backup_YYYYMMDD_HHMMSS`
2. Restore: `cp data/videos_master.json.backup_YYYYMMDD_HHMMSS data/videos_master.json`
3. Verify data integrity

## 📝 **Logging and Monitoring**

### **Log Files**
- **Update logs**: `logs/update_master.log`
- **Rebuild logs**: `logs/rebuild_master.log`
- **GitHub Actions**: Available in workflow artifacts

### **GitHub Issues**
- Rebuild workflow creates summary issue
- Includes statistics and next steps
- Easy to track rebuild history

## 🎯 **Best Practices**

### **When to Rebuild**
- ✅ Monthly metadata refresh
- ✅ After major data structure changes
- ✅ When master list becomes corrupted
- ✅ Before implementing new categorization rules

### **When NOT to Rebuild**
- ❌ For daily maintenance (use regular update)
- ❌ When only a few videos need fixing
- ❌ If you have extensive manual customizations

### **Preparation Steps**
1. **Review current data** - Check what needs preservation
2. **Test with backup** - Run rebuild on a copy first
3. **Plan timing** - Avoid during active categorization work
4. **Notify team** - If working with others

## 🔧 **Troubleshooting**

### **Common Issues**

**1. API Quota Exceeded**
```bash
# Use yt-dlp fallback
unset YOUTUBE_API_KEY
python3 scripts/rebuild_master.py --force
```

**2. Permission Errors**
```bash
# Fix file permissions
chmod +x scripts/*.py
```

**3. Backup Not Created**
```bash
# Check directory permissions
ls -la data/
```

**4. Data Not Preserved**
```bash
# Check if old master list exists
ls -la data/videos_master.json*
```

### **Recovery Commands**
```bash
# List available backups
ls -la data/videos_master.json.backup_*

# Restore from backup
cp data/videos_master.json.backup_20251022_194812 data/videos_master.json

# Verify restoration
python3 scripts/manage_videos.py report
```

## 📊 **Example Rebuild Output**

```
2025-10-22 19:48:12,377 - INFO - 🔄 Rebuild mode requested - delegating to rebuild script
2025-10-22 19:48:12,765 - INFO - 🔑 YouTube API key provided: AIzaSyAtD1...
2025-10-22 19:48:12,769 - INFO - 📦 Created backup: data/videos_master.json.backup_20251022_194812
2025-10-22 19:48:12,771 - INFO - 🚀 Starting COMPLETE master list rebuild...
2025-10-22 19:48:12,772 - INFO - 📊 Found 42 existing videos to preserve data from
2025-10-22 19:48:13,067 - INFO - ✅ Found channel ID via API: UCLXC98YXDDPoaVEQsWPg4ow
2025-10-22 19:48:13,077 - INFO - 🔑 Fetching ALL videos using YouTube Data API v3
2025-10-22 19:48:13,437 - INFO - ✅ Successfully fetched 41 videos from YouTube Data API
2025-10-22 19:48:13,442 - INFO - 🔄 Preserving manual categorizations from old videos...
2025-10-22 19:48:13,442 - INFO - ✅ Preserved manual data for 0 videos
2025-10-22 19:48:13,448 - INFO - ✅ Successfully rebuilt master list with 41 videos
2025-10-22 19:48:13,448 - INFO - 🎉 Rebuild completed successfully!
2025-10-22 19:48:13,448 - INFO - 📊 Total videos: 41
2025-10-22 19:48:13,448 - INFO - 📦 Backup available: data/videos_master.json.backup_20251022_194812
```

---

**Need Help?** Check the logs, review the backup files, or test with a small subset first.
