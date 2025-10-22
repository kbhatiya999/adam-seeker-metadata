#!/usr/bin/env python3
"""
Master List Rebuild Script

This script completely rebuilds the master video list from scratch.
Use this when you need to:
- Refresh all video metadata from YouTube
- Fix corrupted master list
- Start fresh with clean data

WARNING: This will replace your existing master list!
"""

import json
import os
import sys
import requests
import yt_dlp
from datetime import datetime
from typing import Dict, List, Optional
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/rebuild_master.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MasterListRebuilder:
    def __init__(self, master_file: str, channel_url: str, api_key: Optional[str] = None):
        self.master_file = master_file
        self.channel_url = channel_url
        self.api_key = api_key
        self.youtube_api_base = "https://www.googleapis.com/youtube/v3"
        
    def create_backup(self) -> str:
        """Create a timestamped backup of the existing master list"""
        if not os.path.exists(self.master_file):
            logger.info("No existing master file to backup")
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{self.master_file}.backup_{timestamp}"
        
        try:
            with open(self.master_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📦 Created backup: {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            return None
    
    def get_channel_id_from_url(self, channel_url: str) -> Optional[str]:
        """Extract channel ID from YouTube channel URL using API or yt-dlp"""
        if self.api_key:
            logger.info("🔑 Using YouTube Data API to get channel ID")
            try:
                if '@' in channel_url:
                    channel_handle = channel_url.split('@')[-1]
                    search_url = f"{self.youtube_api_base}/search"
                    params = {
                        'part': 'snippet',
                        'q': channel_handle,
                        'type': 'channel',
                        'key': self.api_key
                    }
                    
                    response = requests.get(search_url, params=params)
                    response.raise_for_status()
                    
                    data = response.json()
                    for item in data.get('items', []):
                        if item['snippet']['title'].lower() == 'adam seeker official':
                            channel_id = item['id']['channelId']
                            logger.info(f"✅ Found channel ID via API: {channel_id}")
                            return channel_id
                    
                    if data.get('items'):
                        channel_id = data['items'][0]['id']['channelId']
                        logger.info(f"✅ Using first result channel ID via API: {channel_id}")
                        return channel_id
                        
            except Exception as e:
                logger.error(f"❌ Error getting channel ID from API: {e}")
                return None
        else:
            logger.info("🔄 No API key provided, falling back to yt-dlp for channel ID")
            try:
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(channel_url, download=False)
                    channel_id = info.get('channel_id')
                    if channel_id:
                        logger.info(f"✅ Found channel ID via yt-dlp: {channel_id}")
                    return channel_id
            except Exception as e:
                logger.error(f"❌ Error extracting channel ID with yt-dlp: {e}")
                return None
    
    def fetch_all_videos_youtube_api(self, channel_id: str) -> List[Dict]:
        """Fetch ALL videos using YouTube Data API v3 with pagination"""
        logger.info("🔑 Fetching ALL videos using YouTube Data API v3")
        all_videos = []
        next_page_token = None
        page_count = 0
        max_pages = 20  # Safety limit to prevent infinite loops
        
        try:
            # Get uploads playlist
            uploads_url = f"{self.youtube_api_base}/channels"
            params = {
                'part': 'contentDetails',
                'id': channel_id,
                'key': self.api_key
            }
            
            response = requests.get(uploads_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('items'):
                logger.error("❌ Channel not found or no uploads playlist")
                return []
            
            uploads_playlist_id = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            logger.info(f"📺 Found uploads playlist: {uploads_playlist_id}")
            
            # Fetch all videos with pagination
            while next_page_token is not None or page_count == 0:
                if page_count >= max_pages:
                    logger.warning(f"⚠️ Reached maximum page limit ({max_pages}), stopping")
                    break
                
                page_count += 1
                logger.info(f"📄 Fetching page {page_count}...")
                
                videos_url = f"{self.youtube_api_base}/playlistItems"
                params = {
                    'part': 'snippet',
                    'playlistId': uploads_playlist_id,
                    'maxResults': 50,  # Maximum per page
                    'key': self.api_key
                }
                
                if next_page_token:
                    params['pageToken'] = next_page_token
                
                response = requests.get(videos_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                for item in data.get('items', []):
                    video_info = {
                        'video_id': item['snippet']['resourceId']['videoId'],
                        'title': item['snippet']['title'],
                        'url': f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}",
                        'upload_date': item['snippet']['publishedAt'][:10],
                        'description': item['snippet']['description'][:500],
                        'status': 'uncategorized',
                        'auto_detected': True,
                        'needs_review': True,
                        'last_checked': datetime.now().isoformat()[:10]
                    }
                    all_videos.append(video_info)
                
                # Check for next page
                next_page_token = data.get('nextPageToken')
                if next_page_token:
                    logger.info(f"📄 Found next page token: {next_page_token[:20]}...")
                else:
                    logger.info("📄 No more pages available")
            
            logger.info(f"✅ Successfully fetched {len(all_videos)} videos from YouTube Data API")
            return all_videos
            
        except Exception as e:
            logger.error(f"❌ Error fetching videos from YouTube API: {e}")
            return []
    
    def fetch_all_videos_ytdlp(self) -> List[Dict]:
        """Fetch ALL videos using yt-dlp as fallback"""
        logger.info("🔄 Fetching ALL videos using yt-dlp (fallback method)")
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'playlistend': 1000  # Much higher limit for complete rebuild
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.channel_url, download=False)
                
                videos = []
                for entry in info.get('entries', []):
                    if entry.get('id'):
                        video_info = {
                            'video_id': entry['id'],
                            'title': entry.get('title', 'Unknown Title'),
                            'url': f"https://www.youtube.com/watch?v={entry['id']}",
                            'upload_date': entry.get('upload_date', ''),
                            'duration': entry.get('duration', 0),
                            'description': entry.get('description', '')[:500],
                            'status': 'uncategorized',
                            'auto_detected': True,
                            'needs_review': True,
                            'last_checked': datetime.now().isoformat()[:10]
                        }
                        videos.append(video_info)
                
                logger.info(f"✅ Successfully fetched {len(videos)} videos using yt-dlp")
                return videos
                
        except Exception as e:
            logger.error(f"❌ Error fetching videos with yt-dlp: {e}")
            return []
    
    def preserve_manual_data(self, new_videos: List[Dict], old_videos: List[Dict]) -> List[Dict]:
        """Preserve manual categorizations and notes from old videos"""
        logger.info("🔄 Preserving manual categorizations from old videos...")
        
        # Create lookup for old video data
        old_video_map = {video['video_id']: video for video in old_videos}
        
        preserved_count = 0
        for video in new_videos:
            video_id = video['video_id']
            if video_id in old_video_map:
                old_video = old_video_map[video_id]
                
                # Preserve manual categorizations
                if old_video.get('categories'):
                    video['categories'] = old_video['categories']
                    video['status'] = 'categorized'
                    video['needs_review'] = False
                    preserved_count += 1
                
                # Preserve relevance scores
                if old_video.get('relevance_score'):
                    video['relevance_score'] = old_video['relevance_score']
                
                # Preserve notes
                if old_video.get('notes'):
                    video['notes'] = old_video['notes']
                
                # Preserve key topics
                if old_video.get('key_topics'):
                    video['key_topics'] = old_video['key_topics']
                
                # Preserve transcript file
                if old_video.get('transcript_file'):
                    video['transcript_file'] = old_video['transcript_file']
        
        logger.info(f"✅ Preserved manual data for {preserved_count} videos")
        return new_videos
    
    def rebuild_master_list(self, preserve_manual: bool = True) -> Dict:
        """Main method to rebuild the master video list from scratch"""
        logger.info("🚀 Starting COMPLETE master list rebuild...")
        
        # Load existing master list for preservation
        old_videos = []
        if os.path.exists(self.master_file):
            try:
                with open(self.master_file, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                    old_videos = old_data.get('videos', [])
                logger.info(f"📊 Found {len(old_videos)} existing videos to preserve data from")
            except Exception as e:
                logger.warning(f"⚠️ Could not load existing master list: {e}")
        
        # Get channel ID
        channel_id = self.get_channel_id_from_url(self.channel_url)
        if not channel_id:
            logger.error("❌ Could not extract channel ID")
            return {"success": False, "error": "Could not extract channel ID"}
        
        # Fetch ALL videos
        if self.api_key:
            logger.info("🔑 Using YouTube Data API for complete video discovery")
            all_videos = self.fetch_all_videos_youtube_api(channel_id)
        else:
            logger.info("🔄 Using yt-dlp for complete video discovery (no API key)")
            all_videos = self.fetch_all_videos_ytdlp()
        
        if not all_videos:
            logger.error("❌ No videos fetched")
            return {"success": False, "error": "No videos fetched"}
        
        # Preserve manual data if requested
        if preserve_manual and old_videos:
            all_videos = self.preserve_manual_data(all_videos, old_videos)
        
        # Create new master list
        new_master_data = {
            "videos": all_videos,
            "last_updated": datetime.now().isoformat()[:10],
            "total_videos": len(all_videos),
            "channel_url": self.channel_url,
            "rebuild_date": datetime.now().isoformat()[:10],
            "rebuild_reason": "Complete rebuild from scratch"
        }
        
        # Save new master list
        try:
            with open(self.master_file, 'w', encoding='utf-8') as f:
                json.dump(new_master_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Successfully rebuilt master list with {len(all_videos)} videos")
            return {
                "success": True,
                "total_videos": len(all_videos),
                "preserved_manual": preserve_manual
            }
            
        except Exception as e:
            logger.error(f"❌ Error saving rebuilt master list: {e}")
            return {"success": False, "error": str(e)}

def confirm_rebuild() -> bool:
    """Ask user for confirmation before rebuilding"""
    print("\n" + "="*60)
    print("⚠️  WARNING: MASTER LIST REBUILD")
    print("="*60)
    print("This will COMPLETELY REBUILD your master video list from scratch.")
    print("All existing data will be replaced with fresh data from YouTube.")
    print("\nWhat will happen:")
    print("✅ Create backup of existing master list")
    print("✅ Fetch ALL videos from YouTube channel")
    print("✅ Preserve manual categorizations and notes")
    print("✅ Replace master list with fresh data")
    print("\nWhat you might lose:")
    print("❌ Any manual edits not in the preserved fields")
    print("❌ Custom metadata not in the standard fields")
    print("="*60)
    
    while True:
        response = input("\nAre you sure you want to proceed? (yes/no): ").lower().strip()
        if response in ['yes', 'y']:
            return True
        elif response in ['no', 'n']:
            return False
        else:
            print("Please enter 'yes' or 'no'")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Rebuild master video list from scratch')
    parser.add_argument('--master-file', default='data/videos_master.json',
                       help='Path to master video list file')
    parser.add_argument('--channel-url', default='https://www.youtube.com/@AdamSeekerOfficial',
                       help='YouTube channel URL')
    parser.add_argument('--no-preserve', action='store_true',
                       help='Do not preserve manual categorizations')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    # Configuration
    API_KEY = os.getenv('YOUTUBE_API_KEY')
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Confirmation
    if not args.force:
        if not confirm_rebuild():
            print("❌ Rebuild cancelled by user")
            return
    
    # Log configuration
    if API_KEY:
        logger.info(f"🔑 YouTube API key provided: {API_KEY[:10]}...")
    else:
        logger.info("⚠️  No YouTube API key provided - will use yt-dlp fallback")
    
    # Create backup
    rebuilder = MasterListRebuilder(args.master_file, args.channel_url, API_KEY)
    backup_file = rebuilder.create_backup()
    
    # Rebuild
    result = rebuilder.rebuild_master_list(preserve_manual=not args.no_preserve)
    
    if result['success']:
        logger.info(f"🎉 Rebuild completed successfully!")
        logger.info(f"📊 Total videos: {result['total_videos']}")
        logger.info(f"🔄 Preserved manual data: {result['preserved_manual']}")
        if backup_file:
            logger.info(f"📦 Backup available: {backup_file}")
    else:
        logger.error(f"❌ Rebuild failed: {result.get('error', 'Unknown error')}")
        if backup_file:
            logger.info(f"📦 Backup available for recovery: {backup_file}")

if __name__ == "__main__":
    main()
