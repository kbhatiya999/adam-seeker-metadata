#!/usr/bin/env python3
"""
Configurable Master List Rebuild Script

This script completely rebuilds the master video list from scratch using the configured method.
NO automatic fallbacks - uses the configured method or fails with clear error.

WARNING: This will replace your existing master list!
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
        logging.FileHandler('logs/rebuild_master.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ConfigurableMasterListRebuilder:
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
    
    def fetch_all_videos(self) -> List[Dict]:
        """Fetch ALL videos using the configured method"""
        logger.info(f"🚀 Fetching ALL videos using {self.config.master_list_method} method")
        
        try:
            # For rebuild, we want to fetch a large number of videos
            videos = self.video_fetcher.fetch_videos(self.channel_url, 1000)
            logger.info(f"✅ Successfully fetched {len(videos)} videos using {self.config.master_list_method}")
            return videos
        except Exception as e:
            logger.error(f"❌ Failed to fetch videos using {self.config.master_list_method}: {e}")
            raise RuntimeError(f"Video fetching failed with configured method {self.config.master_list_method}: {e}")
    
    def download_transcripts_for_videos(self, videos: List[Dict], max_videos: int = None) -> None:
        """Download transcripts for videos if requested"""
        if max_videos:
            videos = videos[:max_videos]
        
        logger.info(f"📥 Downloading transcripts for {len(videos)} videos using {self.config.transcript_method}")
        
        success_count = 0
        failed_count = 0
        no_transcript_count = 0
        
        for i, video in enumerate(videos, 1):
            video_id = video['video_id']
            video_url = video['url']
            video_title = video.get('title', 'Unknown Title')
            
            logger.info(f"Processing transcript {i}/{len(videos)}: {video_title[:50]}...")
            
            try:
                # Check if transcript is available
                if not self.transcript_downloader.is_transcript_available(video_id, video_url):
                    logger.info(f"ℹ️ No transcript available for {video_id}")
                    no_transcript_count += 1
                    continue
                
                # Download transcript
                transcript_file = self.transcript_downloader.download_transcript(video_id, video_url)
                
                if transcript_file:
                    # Link transcript to video in master list
                    success = self.transcript_manager.link_transcript_to_video(video_id, transcript_file)
                    if success:
                        success_count += 1
                        logger.info(f"✅ Successfully downloaded transcript for {video_id}")
                    else:
                        failed_count += 1
                        logger.error(f"❌ Failed to link transcript for {video_id}")
                else:
                    failed_count += 1
                    logger.warning(f"⚠️ No transcript file returned for {video_id}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Failed to download transcript for {video_id}: {e}")
        
        logger.info(f"📊 Transcript download results: {success_count} success, {failed_count} failed, {no_transcript_count} no transcript available")
    
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
    
    def rebuild_master_list(self, preserve_manual: bool = True, download_transcripts: bool = False, max_transcripts: int = None) -> Dict:
        """Main method to rebuild the master video list from scratch"""
        logger.info("🚀 Starting COMPLETE master list rebuild using configured method...")
        
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
        all_videos = self.fetch_all_videos()
        
        if not all_videos:
            logger.error("❌ No videos fetched")
            return {"success": False, "error": "No videos fetched"}
        
        # Preserve manual data if requested
        if preserve_manual and old_videos:
            all_videos = self.preserve_manual_data(all_videos, old_videos)
        
        # Download transcripts if requested
        if download_transcripts and all_videos:
            self.download_transcripts_for_videos(all_videos, max_transcripts)
        
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
    parser = argparse.ArgumentParser(description='Rebuild master video list from scratch using configured method')
    parser.add_argument('--no-preserve', action='store_true',
                       help='Do not preserve manual categorizations')
    parser.add_argument('--download-transcripts', action='store_true',
                       help='Download transcripts for all videos')
    parser.add_argument('--max-transcripts', type=int,
                       help='Maximum number of transcripts to download')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Confirmation
    if not args.force:
        if not confirm_rebuild():
            print("❌ Rebuild cancelled by user")
            return
    
    try:
        # Initialize rebuilder
        rebuilder = ConfigurableMasterListRebuilder()
        
        # Create backup
        backup_file = rebuilder.create_backup()
        
        # Rebuild
        result = rebuilder.rebuild_master_list(
            preserve_manual=not args.no_preserve,
            download_transcripts=args.download_transcripts,
            max_transcripts=args.max_transcripts
        )
        
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
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()