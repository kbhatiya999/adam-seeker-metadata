#!/usr/bin/env python3
"""
Configurable Video List Update Script

This script fetches new videos using the configured method (YouTube API or yt-dlp)
and updates the master video list with new entries. NO automatic fallbacks.

Use --rebuild to completely rebuild the master list from scratch.
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import logging
import argparse

# Import our new configurable modules
from config_manager import config_manager
from video_fetchers import VideoFetcherFactory
from transcript_downloaders import TranscriptDownloaderFactory, TranscriptManager

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

class ConfigurableVideoListUpdater:
    def __init__(self):
        self.config = config_manager.load_config()
        self.master_file = self.config.master_file
        self.channel_url = self.config.channel_url
        
        # Initialize video fetcher based on configuration
        fetcher_config = config_manager.get_master_fetcher_config()
        self.video_fetcher = VideoFetcherFactory.create_fetcher(fetcher_config)
        
        # Initialize transcript downloader based on configuration
        transcript_config = config_manager.get_transcript_downloader_config()
        self.transcript_downloader = TranscriptDownloaderFactory.create_downloader(transcript_config)
        self.transcript_manager = TranscriptManager(self.master_file)
        
        logger.info(f"Initialized with master method: {self.config.master_list_method}")
        logger.info(f"Initialized with transcript method: {self.config.transcript_method}")
    
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
            
            logger.info("Master list updated successfully")
            
        except Exception as e:
            logger.error(f"Error saving master list: {e}")
            # Restore backup if save failed
            if os.path.exists(backup_file):
                os.rename(backup_file, self.master_file)
            raise
    
    def get_existing_video_ids(self, master_data: Dict) -> set:
        """Get set of existing video IDs from master list"""
        return {video['video_id'] for video in master_data.get('videos', [])}
    
    def fetch_videos(self, max_videos: int = 50) -> List[Dict]:
        """Fetch videos using the configured method"""
        logger.info(f"🚀 Fetching videos using {self.config.master_list_method} method")
        
        try:
            videos = self.video_fetcher.fetch_videos(self.channel_url, max_videos)
            logger.info(f"✅ Successfully fetched {len(videos)} videos")
            return videos
        except Exception as e:
            logger.error(f"❌ Failed to fetch videos using {self.config.master_list_method}: {e}")
            raise RuntimeError(f"Video fetching failed with configured method {self.config.master_list_method}: {e}")
    
    def download_transcript(self, video_id: str, video_url: str) -> Optional[str]:
        """Download transcript using the configured method"""
        logger.info(f"📥 Downloading transcript for {video_id} using {self.config.transcript_method} method")
        
        try:
            # Check if transcript is available
            if not self.transcript_downloader.is_transcript_available(video_id, video_url):
                logger.info(f"ℹ️ No transcript available for {video_id}")
                return None
            
            # Download transcript
            transcript_file = self.transcript_downloader.download_transcript(video_id, video_url)
            
            if transcript_file:
                # Link transcript to video in master list
                self.transcript_manager.link_transcript_to_video(video_id, transcript_file)
                logger.info(f"✅ Successfully downloaded and linked transcript for {video_id}")
            
            return transcript_file
            
        except Exception as e:
            logger.error(f"❌ Failed to download transcript using {self.config.transcript_method}: {e}")
            raise RuntimeError(f"Transcript downloading failed with configured method {self.config.transcript_method}: {e}")
    
    def update_master_list(self, download_transcripts: bool = False) -> Dict:
        """Main method to update the master video list"""
        logger.info("🚀 Starting configurable video list update...")
        
        # Load current master list
        master_data = self.load_master_list()
        existing_ids = self.get_existing_video_ids(master_data)
        logger.info(f"📊 Current master list has {len(existing_ids)} existing videos")
        
        # Fetch new videos using configured method
        new_videos = self.fetch_videos(self.config.max_videos_per_update)
        
        # Filter out existing videos
        truly_new_videos = [
            video for video in new_videos 
            if video['video_id'] not in existing_ids
        ]
        
        logger.info(f"🔍 Found {len(truly_new_videos)} new videos (filtered from {len(new_videos)} total)")
        
        # Download transcripts for new videos if requested
        if download_transcripts and truly_new_videos:
            logger.info("📥 Downloading transcripts for new videos...")
            for video in truly_new_videos:
                try:
                    self.download_transcript(video['video_id'], video['url'])
                except Exception as e:
                    logger.warning(f"⚠️ Failed to download transcript for {video['video_id']}: {e}")
                    # Continue with other videos even if one fails
        
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
    
    def rebuild_master_list(self, preserve_manual: bool = True, download_transcripts: bool = False) -> Dict:
        """Rebuild the master list from scratch using configured method"""
        logger.info("🚀 Starting configurable master list rebuild...")
        
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
        
        # Fetch ALL videos using configured method
        all_videos = self.fetch_videos(1000)  # Large number for complete rebuild
        
        if not all_videos:
            logger.error("❌ No videos fetched")
            return {"success": False, "error": "No videos fetched"}
        
        # Preserve manual data if requested
        if preserve_manual and old_videos:
            all_videos = self.preserve_manual_data(all_videos, old_videos)
        
        # Download transcripts if requested
        if download_transcripts and all_videos:
            logger.info("📥 Downloading transcripts for all videos...")
            for video in all_videos:
                try:
                    self.download_transcript(video['video_id'], video['url'])
                except Exception as e:
                    logger.warning(f"⚠️ Failed to download transcript for {video['video_id']}: {e}")
                    # Continue with other videos even if one fails
        
        # Create new master list
        new_master_data = {
            "videos": all_videos,
            "last_updated": datetime.now().isoformat()[:10],
            "total_videos": len(all_videos),
            "channel_url": self.channel_url,
            "rebuild_date": datetime.now().isoformat()[:10],
            "rebuild_reason": "Complete rebuild from scratch using configured method",
            "master_method": self.config.master_list_method,
            "transcript_method": self.config.transcript_method
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
                
                # Preserve existing transcript file
                if old_video.get('transcript_file'):
                    video['transcript_file'] = old_video['transcript_file']
                    video['transcript_downloaded'] = old_video.get('transcript_downloaded', False)
        
        logger.info(f"✅ Preserved manual data for {preserved_count} videos")
        return new_videos

def confirm_rebuild() -> bool:
    """Ask user for confirmation before rebuilding"""
    print("\n" + "="*60)
    print("⚠️  WARNING: MASTER LIST REBUILD")
    print("="*60)
    print("This will COMPLETELY REBUILD your master video list from scratch.")
    print("All existing data will be replaced with fresh data from YouTube.")
    print("\nWhat will happen:")
    print("✅ Create backup of existing master list")
    print("✅ Fetch ALL videos from YouTube channel using configured method")
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
    parser = argparse.ArgumentParser(description='Update or rebuild master video list using configured methods')
    parser.add_argument('--rebuild', action='store_true',
                       help='Completely rebuild the master list from scratch')
    parser.add_argument('--download-transcripts', action='store_true',
                       help='Download transcripts for videos')
    parser.add_argument('--no-preserve', action='store_true',
                       help='Do not preserve manual categorizations (rebuild only)')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompts (for rebuild)')
    
    args = parser.parse_args()
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    try:
        # Initialize updater
        updater = ConfigurableVideoListUpdater()
        
        # Handle rebuild mode
        if args.rebuild:
            if not args.force:
                if not confirm_rebuild():
                    print("❌ Rebuild cancelled by user")
                    return
            
            result = updater.rebuild_master_list(
                preserve_manual=not args.no_preserve,
                download_transcripts=args.download_transcripts
            )
            
            if result['success']:
                logger.info(f"🎉 Rebuild completed successfully!")
                logger.info(f"📊 Total videos: {result['total_videos']}")
                logger.info(f"🔄 Preserved manual data: {result['preserved_manual']}")
            else:
                logger.error(f"❌ Rebuild failed: {result.get('error', 'Unknown error')}")
        
        else:
            # Normal update mode
            result = updater.update_master_list(download_transcripts=args.download_transcripts)
            
            if result['updated']:
                logger.info(f"✅ Successfully added {len(result['new_videos'])} new videos")
                logger.info(f"📊 Total videos in master list: {result['total_videos']}")
                
                # Print new video titles for review
                for video in result['new_videos']:
                    logger.info(f"🆕 New: {video['title']} ({video['upload_date']})")
            else:
                logger.info("ℹ️ No new videos found")
        
        # Show transcript stats if transcripts were processed
        if args.download_transcripts:
            stats = updater.transcript_manager.get_transcript_stats()
            logger.info(f"📊 Transcript stats: {stats['videos_with_transcripts']}/{stats['total_videos']} videos have transcripts")
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()