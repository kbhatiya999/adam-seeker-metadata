#!/usr/bin/env python3
"""
Automated Video List Update Script

This script fetches new videos from Adam Seeker's YouTube channel
and updates the master video list with new entries.
"""

import json
import os
import sys
import requests
import yt_dlp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/update_master.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class VideoListUpdater:
    def __init__(self, master_file: str, channel_url: str, api_key: Optional[str] = None):
        self.master_file = master_file
        self.channel_url = channel_url
        self.api_key = api_key
        self.youtube_api_base = "https://www.googleapis.com/youtube/v3"
        
    def load_master_list(self) -> Dict:
        """Load the current master video list"""
        try:
            with open(self.master_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Master file {self.master_file} not found")
            return {"videos": [], "last_updated": None, "total_videos": 0, "channel_url": self.channel_url}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON: {e}")
            return {"videos": [], "last_updated": None, "total_videos": 0, "channel_url": self.channel_url}
    
    def save_master_list(self, data: Dict) -> None:
        """Save the updated master video list"""
        try:
            # Create backup
            backup_file = f"{self.master_file}.backup"
            if os.path.exists(self.master_file):
                os.rename(self.master_file, backup_file)
            
            # Save updated data
            with open(self.master_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Master list updated successfully")
            
        except Exception as e:
            logger.error(f"Error saving master list: {e}")
            # Restore backup if save failed
            if os.path.exists(backup_file):
                os.rename(backup_file, self.master_file)
            raise
    
    def get_channel_id_from_url(self, channel_url: str) -> Optional[str]:
        """Extract channel ID from YouTube channel URL using API or yt-dlp"""
        if self.api_key:
            logger.info("🔑 Using YouTube Data API to get channel ID")
            try:
                # Extract channel handle from URL
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
                    
                    # If exact match not found, return first result
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
    
    def fetch_videos_youtube_api(self, channel_id: str, max_results: int = 50) -> List[Dict]:
        """Fetch videos using YouTube Data API v3"""
        logger.info(f"🔑 Fetching videos using YouTube Data API v3 (max: {max_results})")
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
            
            # Get videos from uploads playlist
            videos_url = f"{self.youtube_api_base}/playlistItems"
            params = {
                'part': 'snippet',
                'playlistId': uploads_playlist_id,
                'maxResults': max_results,
                'key': self.api_key
            }
            
            response = requests.get(videos_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            videos = []
            
            for item in data.get('items', []):
                video_info = {
                    'video_id': item['snippet']['resourceId']['videoId'],
                    'title': item['snippet']['title'],
                    'url': f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}",
                    'upload_date': item['snippet']['publishedAt'][:10],  # YYYY-MM-DD
                    'description': item['snippet']['description'][:500],  # Truncate long descriptions
                    'status': 'uncategorized',
                    'auto_detected': True,
                    'needs_review': True,
                    'last_checked': datetime.now().isoformat()[:10]
                }
                videos.append(video_info)
            
            logger.info(f"✅ Successfully fetched {len(videos)} videos from YouTube Data API")
            return videos
            
        except Exception as e:
            logger.error(f"❌ Error fetching videos from YouTube API: {e}")
            return []
    
    def fetch_videos_ytdlp(self) -> List[Dict]:
        """Fetch videos using yt-dlp as fallback"""
        logger.info("🔄 Fetching videos using yt-dlp (fallback method)")
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'playlistend': 50  # Limit to last 50 videos
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
    
    def get_existing_video_ids(self, master_data: Dict) -> set:
        """Get set of existing video IDs from master list"""
        return {video['video_id'] for video in master_data.get('videos', [])}
    
    def update_master_list(self) -> Dict:
        """Main method to update the master video list"""
        logger.info("🚀 Starting video list update...")
        
        # Load current master list
        master_data = self.load_master_list()
        existing_ids = self.get_existing_video_ids(master_data)
        logger.info(f"📊 Current master list has {len(existing_ids)} existing videos")
        
        # Get channel ID
        channel_id = self.get_channel_id_from_url(self.channel_url)
        if not channel_id:
            logger.error("❌ Could not extract channel ID")
            return {"new_videos": [], "total_videos": len(master_data.get('videos', [])), "updated": False}
        
        # Fetch new videos
        if self.api_key:
            logger.info("🔑 Using YouTube Data API for video discovery")
            new_videos = self.fetch_videos_youtube_api(channel_id)
        else:
            logger.info("🔄 Using yt-dlp for video discovery (no API key)")
            new_videos = self.fetch_videos_ytdlp()
        
        # Filter out existing videos
        truly_new_videos = [
            video for video in new_videos 
            if video['video_id'] not in existing_ids
        ]
        
        logger.info(f"🔍 Found {len(truly_new_videos)} new videos (filtered from {len(new_videos)} total)")
        
        # Add new videos to master list
        master_data['videos'].extend(truly_new_videos)
        master_data['last_updated'] = datetime.now().isoformat()[:10]
        master_data['total_videos'] = len(master_data['videos'])
        
        # Save updated master list
        self.save_master_list(master_data)
        
        return {
            'new_videos': truly_new_videos,
            'total_videos': master_data['total_videos'],
            'updated': len(truly_new_videos) > 0
        }

def main():
    """Main entry point"""
    # Configuration
    MASTER_FILE = "data/videos_master.json"
    CHANNEL_URL = "https://www.youtube.com/@AdamSeekerOfficial"
    API_KEY = os.getenv('YOUTUBE_API_KEY')  # Set this as environment variable
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Log configuration
    if API_KEY:
        logger.info(f"🔑 YouTube API key provided: {API_KEY[:10]}...")
    else:
        logger.info("⚠️  No YouTube API key provided - will use yt-dlp fallback")
    
    # Initialize updater
    updater = VideoListUpdater(MASTER_FILE, CHANNEL_URL, API_KEY)
    
    # Update master list
    result = updater.update_master_list()
    
    if result['updated']:
        logger.info(f"✅ Successfully added {len(result['new_videos'])} new videos")
        logger.info(f"📊 Total videos in master list: {result['total_videos']}")
        
        # Print new video titles for review
        for video in result['new_videos']:
            logger.info(f"🆕 New: {video['title']} ({video['upload_date']})")
    else:
        logger.info("ℹ️ No new videos found")
    
    return result

if __name__ == "__main__":
    main()
