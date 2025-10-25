#!/usr/bin/env python3
"""
Video Fetchers

Configurable video fetching implementations with NO automatic fallbacks.
Each method is independent and will fail clearly if not properly configured.
"""

import os
import requests
import yt_dlp
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class VideoFetcher(ABC):
    """Abstract base class for video fetchers"""
    
    @abstractmethod
    def fetch_videos(self, channel_url: str, max_videos: int = 50) -> List[Dict]:
        """Fetch videos from channel"""
        pass
    
    @abstractmethod
    def get_channel_id(self, channel_url: str) -> Optional[str]:
        """Get channel ID from URL"""
        pass

class YouTubeAPIFetcher(VideoFetcher):
    """YouTube Data API v3 video fetcher"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("YouTube API key is required for YouTubeAPIFetcher")
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
        logger.info("Initialized YouTube Data API fetcher")
    
    def get_channel_id(self, channel_url: str) -> Optional[str]:
        """Get channel ID using YouTube API"""
        logger.info("🔑 Getting channel ID using YouTube Data API")
        
        try:
            if '@' in channel_url:
                channel_handle = channel_url.split('@')[-1]
                search_url = f"{self.base_url}/search"
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
            raise RuntimeError(f"Failed to get channel ID using YouTube API: {e}")
        
        return None
    
    def fetch_videos(self, channel_url: str, max_videos: int = 50) -> List[Dict]:
        """Fetch videos using YouTube Data API v3"""
        logger.info(f"🔑 Fetching videos using YouTube Data API v3 (max: {max_videos})")
        
        try:
            # Get channel ID first
            channel_id = self.get_channel_id(channel_url)
            if not channel_id:
                raise RuntimeError("Could not extract channel ID using YouTube API")
            
            # Get uploads playlist
            uploads_url = f"{self.base_url}/channels"
            params = {
                'part': 'contentDetails',
                'id': channel_id,
                'key': self.api_key
            }
            
            response = requests.get(uploads_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('items'):
                raise RuntimeError("Channel not found or no uploads playlist")
            
            uploads_playlist_id = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            logger.info(f"📺 Found uploads playlist: {uploads_playlist_id}")
            
            # Get videos from uploads playlist
            videos_url = f"{self.base_url}/playlistItems"
            params = {
                'part': 'snippet',
                'playlistId': uploads_playlist_id,
                'maxResults': min(max_videos, 50),  # API limit is 50 per request
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
                    'upload_date': item['snippet']['publishedAt'][:10],
                    'description': item['snippet']['description'][:500],
                    'status': 'uncategorized',
                    'auto_detected': True,
                    'needs_review': True,
                    'last_checked': datetime.now().isoformat()[:10]
                }
                videos.append(video_info)
            
            logger.info("✅ Successfully fetched videos using YouTube Data API")
            return videos
                    
        except Exception as e:
            logger.error(f"❌ Error fetching videos from YouTube API: {e}")
            raise RuntimeError(f"Failed to fetch videos using YouTube API: {e}")

class YtDlpFetcher(VideoFetcher):
    """yt-dlp video fetcher with optional cookies and proxy support"""
    
    def __init__(self, cookies_file: Optional[str] = None, use_proxy: bool = False, proxy: Optional[str] = None):
        self.cookies_file = cookies_file
        self.use_proxy = use_proxy
        self.proxy = proxy
        
        # Validate cookies file if provided
        if cookies_file and not os.path.exists(cookies_file):
            logger.warning(f"Cookies file specified but not found: {cookies_file}")
        
        logger.info("Initialized yt-dlp fetcher")
        if cookies_file:
            logger.info(f"Using cookies file: {cookies_file}")
        if use_proxy and proxy:
            logger.info(f"Using proxy: {proxy[:20]}...")
    
    def get_channel_id(self, channel_url: str) -> Optional[str]:
        """Get channel ID using yt-dlp"""
        logger.info("🔄 Getting channel ID using yt-dlp")
        
        try:
            ydl_opts = {'quiet': True}
            
            # Add cookies if specified
            if self.cookies_file:
                ydl_opts['cookiesfrombrowser'] = ('chrome',)  # Default browser
                ydl_opts['cookiefile'] = self.cookies_file
            
            # Add proxy if specified
            if self.use_proxy and self.proxy:
                ydl_opts['proxy'] = self.proxy
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                channel_id = info.get('channel_id')
                if channel_id:
                    logger.info(f"✅ Found channel ID via yt-dlp: {channel_id}")
                return channel_id
                
        except Exception as e:
            logger.error(f"❌ Error extracting channel ID with yt-dlp: {e}")
            raise RuntimeError(f"Failed to get channel ID using yt-dlp: {e}")
    
    def fetch_videos(self, channel_url: str, max_videos: int = 50) -> List[Dict]:
        """Fetch videos using yt-dlp"""
        logger.info(f"🔄 Fetching videos using yt-dlp (max: {max_videos})")
        
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'playlistend': max_videos
            }
            
            # Add cookies if specified
            if self.cookies_file:
                ydl_opts['cookiesfrombrowser'] = ('chrome',)  # Default browser
                ydl_opts['cookiefile'] = self.cookies_file
            
            # Add proxy if specified
            if self.use_proxy and self.proxy:
                ydl_opts['proxy'] = self.proxy
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                
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
                
                logger.info("✅ Successfully fetched videos using yt-dlp")
                return videos
                
        except Exception as e:
            logger.error(f"❌ Error fetching videos with yt-dlp: {e}")
            raise RuntimeError(f"Failed to fetch videos using yt-dlp: {e}")

class VideoFetcherFactory:
    """Factory for creating video fetchers based on configuration"""
    
    @staticmethod
    def create_fetcher(config: Dict[str, Any]) -> VideoFetcher:
        """Create appropriate video fetcher based on configuration"""
        method = config.get('method')
        
        if method == 'youtube_api':
            api_key = config.get('api_key')
            if not api_key:
                raise ValueError("API key is required for youtube_api method")
            return YouTubeAPIFetcher(api_key)
        
        elif method == 'ytdlp':
            return YtDlpFetcher(
                cookies_file=config.get('cookies_file'),
                use_proxy=config.get('use_proxy', False),
                proxy=config.get('proxy')
            )
        
        else:
            raise ValueError(f"Unknown video fetching method: {method}")