#!/usr/bin/env python3
"""
Transcript Management Script

This script manages transcript downloading and linking for videos in the master list.
Uses the configured transcript downloading method with NO automatic fallbacks.
"""

import os
import sys
import logging
import argparse
from typing import List, Dict

# Import our configurable modules
from config_manager import config_manager
from transcript_downloaders import TranscriptDownloaderFactory, TranscriptManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/manage_transcripts.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TranscriptManagerCLI:
    def __init__(self):
        self.config = config_manager.load_config()
        self.master_file = self.config.master_file
        
        # Initialize transcript downloader based on configuration
        transcript_config = config_manager.get_transcript_downloader_config()
        self.transcript_downloader = TranscriptDownloaderFactory.create_downloader(transcript_config)
        self.transcript_manager = TranscriptManager(self.master_file)
        
        logger.info(f"Initialized with transcript method: {self.config.transcript_method}")
    
    def download_transcript_for_video(self, video_id: str, video_url: str) -> bool:
        """Download transcript for a specific video"""
        logger.info(f"📥 Downloading transcript for video {video_id}")
        
        try:
            # Check if transcript is available
            if not self.transcript_downloader.is_transcript_available(video_id, video_url):
                logger.info(f"ℹ️ No transcript available for {video_id}")
                return False
            
            # Download transcript
            transcript_file = self.transcript_downloader.download_transcript(video_id, video_url)
            
            if transcript_file:
                # Link transcript to video in master list
                success = self.transcript_manager.link_transcript_to_video(video_id, transcript_file)
                if success:
                    logger.info(f"✅ Successfully downloaded and linked transcript for {video_id}")
                    return True
                else:
                    logger.error(f"❌ Failed to link transcript to video {video_id}")
                    return False
            else:
                logger.warning(f"⚠️ Transcript download completed but no file returned for {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to download transcript for {video_id}: {e}")
            return False
    
    def download_transcripts_for_videos(self, videos: List[Dict], max_videos: int = None) -> Dict[str, int]:
        """Download transcripts for a list of videos"""
        if max_videos:
            videos = videos[:max_videos]
        
        logger.info(f"📥 Downloading transcripts for {len(videos)} videos")
        
        success_count = 0
        failed_count = 0
        no_transcript_count = 0
        
        for i, video in enumerate(videos, 1):
            video_id = video['video_id']
            video_url = video['url']
            video_title = video.get('title', 'Unknown Title')
            
            logger.info(f"Processing {i}/{len(videos)}: {video_title[:50]}...")
            
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
        
        return {
            'success': success_count,
            'failed': failed_count,
            'no_transcript': no_transcript_count,
            'total': len(videos)
        }
    
    def download_missing_transcripts(self, max_videos: int = None) -> Dict[str, int]:
        """Download transcripts for videos that don't have them"""
        videos_without_transcripts = self.transcript_manager.get_videos_without_transcripts()
        
        if not videos_without_transcripts:
            logger.info("✅ All videos already have transcripts")
            return {'success': 0, 'failed': 0, 'no_transcript': 0, 'total': 0}
        
        logger.info(f"📝 Found {len(videos_without_transcripts)} videos without transcripts")
        return self.download_transcripts_for_videos(videos_without_transcripts, max_videos)
    
    def show_transcript_stats(self) -> None:
        """Show statistics about transcript availability"""
        stats = self.transcript_manager.get_transcript_stats()
        
        print("\n" + "="*60)
        print("📊 TRANSCRIPT STATISTICS")
        print("="*60)
        print(f"Total Videos: {stats['total_videos']}")
        print(f"Videos with Transcripts: {stats['videos_with_transcripts']}")
        print(f"Transcript Files Exist: {stats['transcript_files_exist']}")
        print(f"Videos without Transcripts: {stats['videos_without_transcripts']}")
        
        if stats['total_videos'] > 0:
            percentage = (stats['videos_with_transcripts'] / stats['total_videos']) * 100
            print(f"Coverage: {percentage:.1f}%")
        
        print("="*60)
    
    def list_videos_without_transcripts(self) -> None:
        """List videos that don't have transcripts"""
        videos_without_transcripts = self.transcript_manager.get_videos_without_transcripts()
        
        if not videos_without_transcripts:
            print("✅ All videos have transcripts!")
            return
        
        print(f"\n📝 Videos without transcripts ({len(videos_without_transcripts)}):")
        print("-" * 80)
        
        for i, video in enumerate(videos_without_transcripts, 1):
            title = video.get('title', 'Unknown Title')
            video_id = video.get('video_id', 'Unknown ID')
            upload_date = video.get('upload_date', 'Unknown Date')
            
            print(f"{i:3d}. {title[:60]:<60} ({video_id}) - {upload_date}")
    
    def check_transcript_availability(self, video_id: str, video_url: str) -> None:
        """Check if transcript is available for a specific video"""
        logger.info(f"🔍 Checking transcript availability for {video_id}")
        
        try:
            available = self.transcript_downloader.is_transcript_available(video_id, video_url)
            if available:
                print(f"✅ Transcript is available for {video_id}")
            else:
                print(f"❌ No transcript available for {video_id}")
        except Exception as e:
            print(f"❌ Error checking transcript availability: {e}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Manage video transcripts using configured method')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Download transcript for specific video
    download_parser = subparsers.add_parser('download', help='Download transcript for specific video')
    download_parser.add_argument('video_id', help='Video ID to download transcript for')
    download_parser.add_argument('video_url', help='Video URL')
    
    # Download missing transcripts
    missing_parser = subparsers.add_parser('download-missing', help='Download transcripts for videos without them')
    missing_parser.add_argument('--max-videos', type=int, help='Maximum number of videos to process')
    
    # Download transcripts for specific videos
    videos_parser = subparsers.add_parser('download-videos', help='Download transcripts for specific videos')
    videos_parser.add_argument('--video-ids', nargs='+', required=True, help='Video IDs to process')
    videos_parser.add_argument('--max-videos', type=int, help='Maximum number of videos to process')
    
    # Show statistics
    subparsers.add_parser('stats', help='Show transcript statistics')
    
    # List videos without transcripts
    subparsers.add_parser('list-missing', help='List videos without transcripts')
    
    # Check availability
    check_parser = subparsers.add_parser('check', help='Check if transcript is available for video')
    check_parser.add_argument('video_id', help='Video ID to check')
    check_parser.add_argument('video_url', help='Video URL')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    try:
        # Initialize manager
        manager = TranscriptManagerCLI()
        
        if args.command == 'download':
            success = manager.download_transcript_for_video(args.video_id, args.video_url)
            if success:
                print("✅ Transcript downloaded successfully")
            else:
                print("❌ Failed to download transcript")
                sys.exit(1)
        
        elif args.command == 'download-missing':
            result = manager.download_missing_transcripts(args.max_videos)
            print(f"\n📊 Download Results:")
            print(f"  Success: {result['success']}")
            print(f"  Failed: {result['failed']}")
            print(f"  No transcript available: {result['no_transcript']}")
            print(f"  Total processed: {result['total']}")
        
        elif args.command == 'download-videos':
            # Load master list to get video URLs
            import json
            with open(manager.master_file, 'r', encoding='utf-8') as f:
                master_data = json.load(f)
            
            videos_to_process = []
            for video in master_data.get('videos', []):
                if video['video_id'] in args.video_ids:
                    videos_to_process.append(video)
            
            if not videos_to_process:
                print("❌ No matching videos found in master list")
                sys.exit(1)
            
            result = manager.download_transcripts_for_videos(videos_to_process, args.max_videos)
            print(f"\n📊 Download Results:")
            print(f"  Success: {result['success']}")
            print(f"  Failed: {result['failed']}")
            print(f"  No transcript available: {result['no_transcript']}")
            print(f"  Total processed: {result['total']}")
        
        elif args.command == 'stats':
            manager.show_transcript_stats()
        
        elif args.command == 'list-missing':
            manager.list_videos_without_transcripts()
        
        elif args.command == 'check':
            manager.check_transcript_availability(args.video_id, args.video_url)
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()