#!/usr/bin/env python3
"""
Setup script for video list automation

This script updates the existing master list structure to support
automation features and validates the setup.
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List

def update_master_list_structure(master_file: str) -> None:
    """Update the master list structure to include automation fields"""
    print(f"📝 Updating master list structure: {master_file}")
    
    try:
        # Load existing data
        with open(master_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Ensure all required fields exist
        if 'videos' not in data:
            data['videos'] = []
        
        if 'last_updated' not in data:
            data['last_updated'] = None
        
        if 'total_videos' not in data:
            data['total_videos'] = len(data['videos'])
        
        if 'channel_url' not in data:
            data['channel_url'] = "https://www.youtube.com/@AdamSeekerOfficial"
        
        # Update each video with automation fields
        updated_count = 0
        for video in data['videos']:
            # Add automation fields if they don't exist
            if 'status' not in video:
                video['status'] = 'categorized'  # Assume existing videos are categorized
                updated_count += 1
            
            if 'auto_detected' not in video:
                video['auto_detected'] = False  # Existing videos were manually added
                updated_count += 1
            
            if 'needs_review' not in video:
                video['needs_review'] = False  # Existing videos don't need review
                updated_count += 1
            
            if 'last_checked' not in video:
                video['last_checked'] = datetime.now().isoformat()[:10]
                updated_count += 1
            
            # Ensure required fields exist
            if 'video_id' not in video:
                print(f"⚠️  Warning: Video missing video_id: {video.get('title', 'Unknown')}")
            
            if 'title' not in video:
                video['title'] = 'Unknown Title'
            
            if 'url' not in video:
                if 'video_id' in video:
                    video['url'] = f"https://www.youtube.com/watch?v={video['video_id']}"
            
            if 'upload_date' not in video:
                video['upload_date'] = 'Unknown'
            
            if 'categories' not in video:
                video['categories'] = []
            
            if 'relevance_score' not in video:
                video['relevance_score'] = None
            
            if 'notes' not in video:
                video['notes'] = ""
        
        # Update metadata
        data['last_updated'] = datetime.now().isoformat()[:10]
        data['total_videos'] = len(data['videos'])
        
        # Create backup
        backup_file = f"{master_file}.backup"
        if os.path.exists(master_file):
            os.rename(master_file, backup_file)
            print(f"📦 Created backup: {backup_file}")
        
        # Save updated data
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Updated {updated_count} videos with automation fields")
        print(f"📊 Total videos: {len(data['videos'])}")
        
    except FileNotFoundError:
        print(f"❌ Master file {master_file} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error updating master list: {e}")
        sys.exit(1)

def validate_setup() -> None:
    """Validate that all required files and directories exist"""
    print("\n🔍 Validating setup...")
    
    required_files = [
        'data/videos_master.json',
        'scripts/update_master.py',
        'scripts/manage_videos.py',
        'requirements.txt',
        '.github/workflows/update-videos.yml'
    ]
    
    required_dirs = [
        'data',
        'scripts',
        'logs',
        '.github/workflows'
    ]
    
    missing_files = []
    missing_dirs = []
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            missing_dirs.append(dir_path)
    
    if missing_files:
        print("❌ Missing files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
    
    if missing_dirs:
        print("❌ Missing directories:")
        for dir_path in missing_dirs:
            print(f"  - {dir_path}")
    
    if not missing_files and not missing_dirs:
        print("✅ All required files and directories exist")
    else:
        print("\n💡 Run this script again after creating missing files/directories")
        sys.exit(1)

def create_sample_config() -> None:
    """Create a sample configuration file"""
    config_content = """# Video List Automation Configuration

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

# Categories (comma-separated)
DEFAULT_CATEGORIES=critique-of-islam,theology,apologetics,debate
"""
    
    config_file = 'config.env'
    if not os.path.exists(config_file):
        with open(config_file, 'w') as f:
            f.write(config_content)
        print(f"📝 Created sample configuration: {config_file}")
        print("   Edit this file with your actual API keys and settings")
    else:
        print(f"ℹ️  Configuration file already exists: {config_file}")

def main():
    """Main setup function"""
    print("🚀 Setting up video list automation...")
    print("=" * 50)
    
    # Validate setup
    validate_setup()
    
    # Update master list structure
    master_file = 'data/videos_master.json'
    update_master_list_structure(master_file)
    
    # Create sample configuration
    create_sample_config()
    
    print("\n" + "=" * 50)
    print("✅ Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Get a YouTube Data API key from Google Cloud Console")
    print("2. Set the YOUTUBE_API_KEY environment variable or edit config.env")
    print("3. Test the update script: python scripts/update_master.py")
    print("4. Set up GitHub Actions secrets for automated updates")
    print("5. Use the management script: python scripts/manage_videos.py --help")
    
    print("\n🔧 GitHub Actions Setup:")
    print("1. Go to your repository settings")
    print("2. Navigate to Secrets and Variables > Actions")
    print("3. Add a new secret: YOUTUBE_API_KEY")
    print("4. The workflow will run automatically daily at 6 AM UTC")

if __name__ == "__main__":
    main()
