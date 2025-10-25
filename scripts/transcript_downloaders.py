#!/usr/bin/env python3
"""
Transcript Downloaders

Configurable transcript downloading implementations with NO automatic fallbacks.
Each method is independent and will fail clearly if not properly configured.
"""

import os
import json
import yt_dlp
import logging
import requests
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)

class TranscriptDownloader(ABC):
    """Abstract base class for transcript downloaders"""
    
    @abstractmethod
    def download_transcript(self, video_id: str, video_url: str) -> Optional[str]:
        """Download transcript for a video and return file path"""
        pass
    
    @abstractmethod
    def is_transcript_available(self, video_id: str, video_url: str) -> bool:
        """Check if transcript is available for a video"""
        pass

class YtDlpTranscriptDownloader(TranscriptDownloader):
    """yt-dlp transcript downloader with optional cookies and proxy support"""
    
    def __init__(self, cookies_file: Optional[str] = None, use_proxy: bool = False, proxy: Optional[str] = None):
        self.cookies_file = cookies_file
        self.use_proxy = use_proxy
        self.proxy = proxy
        self.transcript_dir = "data/transcripts"
        
        # Create transcript directory if it doesn't exist
        os.makedirs(self.transcript_dir, exist_ok=True)
        
        # Validate cookies file if provided
        if cookies_file and not os.path.exists(cookies_file):
            logger.warning(f"Cookies file specified but not found: {cookies_file}")
        
        logger.info("Initialized yt-dlp transcript downloader")
        if cookies_file:
            logger.info(f"Using cookies file: {cookies_file}")
        if use_proxy and proxy:
            logger.info(f"Using proxy: {proxy[:20]}...")
    
    def is_transcript_available(self, video_id: str, video_url: str) -> bool:
        """Check if transcript is available using yt-dlp"""
        logger.info(f"🔍 Checking transcript availability for {video_id} using yt-dlp")
        
        try:
            ydl_opts = {
                'quiet': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'skip_download': True
            }
            
            # Add cookies if specified
            if self.cookies_file:
                ydl_opts['cookiesfrombrowser'] = ('chrome',)  # Default browser
                ydl_opts['cookiefile'] = self.cookies_file
            
            # Add proxy if specified
            if self.use_proxy and self.proxy:
                ydl_opts['proxy'] = self.proxy
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                # Check if subtitles are available
                subtitles = info.get('subtitles', {})
                automatic_captions = info.get('automatic_captions', {})
                
                has_subtitles = bool(subtitles)
                has_auto_captions = bool(automatic_captions)
                
                logger.info(f"Transcript availability - Manual: {has_subtitles}, Auto: {has_auto_captions}")
                return has_subtitles or has_auto_captions
                
        except Exception as e:
            logger.error(f"❌ Error checking transcript availability with yt-dlp: {e}")
            return False
    
    def download_transcript(self, video_id: str, video_url: str) -> Optional[str]:
        """Download transcript using yt-dlp"""
        logger.info(f"📥 Downloading transcript for {video_id} using yt-dlp")
        
        try:
            # Define output filename
            output_file = os.path.join(self.transcript_dir, f"{video_id}.vtt")
            
            ydl_opts = {
                'quiet': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'skip_download': True,
                'subtitlesformat': 'vtt',
                'outtmpl': output_file.replace('.vtt', '.%(ext)s')
            }
            
            # Add cookies if specified
            if self.cookies_file:
                ydl_opts['cookiesfrombrowser'] = ('chrome',)  # Default browser
                ydl_opts['cookiefile'] = self.cookies_file
            
            # Add proxy if specified
            if self.use_proxy and self.proxy:
                ydl_opts['proxy'] = self.proxy
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            # Check if file was created
            if os.path.exists(output_file):
                logger.info(f"✅ Successfully downloaded transcript: {output_file}")
                return output_file
            else:
                logger.warning(f"⚠️ Transcript download completed but file not found: {output_file}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error downloading transcript with yt-dlp: {e}")
            raise RuntimeError(f"Failed to download transcript using yt-dlp: {e}")

class YouTubeTranscriptAPIDownloader(TranscriptDownloader):
    """YouTube Transcript API downloader with optional proxy support"""
    
    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.transcript_dir = "data/transcripts"
        
        # Create transcript directory if it doesn't exist
        os.makedirs(self.transcript_dir, exist_ok=True)
        
        # Try to import youtube_transcript_api
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api.formatters import VTTFormatter
            self.YouTubeTranscriptApi = YouTubeTranscriptApi
            self.VTTFormatter = VTTFormatter
        except ImportError:
            raise ImportError("youtube-transcript-api is required for this method. Install with: pip install youtube-transcript-api")
        
        logger.info("Initialized YouTube Transcript API downloader")
        if proxy:
            logger.info(f"Using proxy: {proxy[:20]}...")
    
    def is_transcript_available(self, video_id: str, video_url: str) -> bool:
        """Check if transcript is available using YouTube Transcript API"""
        logger.info(f"🔍 Checking transcript availability for {video_id} using YouTube Transcript API")
        
        try:
            # Set up proxy if specified
            if self.proxy:
                import os
                os.environ['HTTP_PROXY'] = self.proxy
                os.environ['HTTPS_PROXY'] = self.proxy
            
            transcript_list = self.YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Check if any transcripts are available
            has_transcripts = False
            for transcript in transcript_list:
                has_transcripts = True
                break
            
            logger.info(f"Transcript availability: {has_transcripts}")
            return has_transcripts
            
        except Exception as e:
            logger.error(f"❌ Error checking transcript availability with YouTube Transcript API: {e}")
            return False
    
    def download_transcript(self, video_id: str, video_url: str) -> Optional[str]:
        """Download transcript using YouTube Transcript API"""
        logger.info(f"📥 Downloading transcript for {video_id} using YouTube Transcript API")
        
        try:
            # Set up proxy if specified
            if self.proxy:
                import os
                os.environ['HTTP_PROXY'] = self.proxy
                os.environ['HTTPS_PROXY'] = self.proxy
            
            # Get transcript list
            transcript_list = self.YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try to get English transcript first, then any available
            transcript = None
            try:
                transcript = transcript_list.find_transcript(['en'])
            except:
                # If no English transcript, get the first available
                for t in transcript_list:
                    transcript = t
                    break
            
            if not transcript:
                logger.warning(f"⚠️ No transcript found for {video_id}")
                return None
            
            # Fetch the transcript
            transcript_data = transcript.fetch()
            
            # Convert to VTT format
            formatter = self.VTTFormatter()
            vtt_content = formatter.format_transcript(transcript_data)
            
            # Save to file
            output_file = os.path.join(self.transcript_dir, f"{video_id}.vtt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(vtt_content)
            
            logger.info(f"✅ Successfully downloaded transcript: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"❌ Error downloading transcript with YouTube Transcript API: {e}")
            raise RuntimeError(f"Failed to download transcript using YouTube Transcript API: {e}")

class TranscriptDownloaderFactory:
    """Factory for creating transcript downloaders based on configuration"""
    
    @staticmethod
    def create_downloader(config: Dict[str, Any]) -> TranscriptDownloader:
        """Create appropriate transcript downloader based on configuration"""
        method = config.get('method')
        
        if method == 'ytdlp':
            return YtDlpTranscriptDownloader(
                cookies_file=config.get('cookies_file'),
                use_proxy=config.get('use_proxy', False),
                proxy=config.get('proxy')
            )
        
        elif method == 'youtube_transcript_api':
            return YouTubeTranscriptAPIDownloader(
                proxy=config.get('proxy')
            )
        
        else:
            raise ValueError(f"Unknown transcript downloading method: {method}")

class TranscriptManager:
    """Manages transcript operations and linking to videos"""
    
    def __init__(self, master_file: str):
        self.master_file = master_file
        self.transcript_dir = "data/transcripts"
    
    def link_transcript_to_video(self, video_id: str, transcript_file: str) -> bool:
        """Link transcript file to video in master list"""
        try:
            # Load master list
            with open(self.master_file, 'r', encoding='utf-8') as f:
                master_data = json.load(f)
            
            # Find video and update transcript file path
            for video in master_data.get('videos', []):
                if video['video_id'] == video_id:
                    video['transcript_file'] = transcript_file
                    video['transcript_downloaded'] = True
                    video['transcript_download_date'] = datetime.now().isoformat()[:10]
                    
                    # Save updated master list
                    with open(self.master_file, 'w', encoding='utf-8') as f:
                        json.dump(master_data, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"✅ Linked transcript to video {video_id}")
                    return True
            
            logger.warning(f"⚠️ Video {video_id} not found in master list")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error linking transcript to video: {e}")
            return False
    
    def get_videos_without_transcripts(self) -> List[Dict]:
        """Get list of videos that don't have transcripts"""
        try:
            with open(self.master_file, 'r', encoding='utf-8') as f:
                master_data = json.load(f)
            
            videos_without_transcripts = []
            for video in master_data.get('videos', []):
                if not video.get('transcript_file') or not os.path.exists(video.get('transcript_file', '')):
                    videos_without_transcripts.append(video)
            
            return videos_without_transcripts
            
        except Exception as e:
            logger.error(f"❌ Error getting videos without transcripts: {e}")
            return []
    
    def get_transcript_stats(self) -> Dict[str, int]:
        """Get statistics about transcript availability"""
        try:
            with open(self.master_file, 'r', encoding='utf-8') as f:
                master_data = json.load(f)
            
            total_videos = len(master_data.get('videos', []))
            videos_with_transcripts = 0
            transcript_files_exist = 0
            
            for video in master_data.get('videos', []):
                if video.get('transcript_file'):
                    videos_with_transcripts += 1
                    if os.path.exists(video.get('transcript_file', '')):
                        transcript_files_exist += 1
            
            return {
                'total_videos': total_videos,
                'videos_with_transcripts': videos_with_transcripts,
                'transcript_files_exist': transcript_files_exist,
                'videos_without_transcripts': total_videos - videos_with_transcripts
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting transcript stats: {e}")
            return {'total_videos': 0, 'videos_with_transcripts': 0, 'transcript_files_exist': 0, 'videos_without_transcripts': 0}