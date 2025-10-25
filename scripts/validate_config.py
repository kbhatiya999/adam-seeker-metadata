#!/usr/bin/env python3
"""
Configuration Validation Script

This script validates the configuration and tests the configured methods
to ensure they work properly before running the main scripts.
"""

import os
import sys
import logging
from typing import Dict, Any

# Import our configurable modules
from config_manager import config_manager
from video_fetchers import VideoFetcherFactory
from transcript_downloaders import TranscriptDownloaderFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/validate_config.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ConfigValidator:
    def __init__(self):
        self.config = None
        self.video_fetcher = None
        self.transcript_downloader = None
    
    def validate_configuration(self) -> bool:
        """Validate the configuration file and settings"""
        logger.info("🔍 Validating configuration...")
        
        try:
            # Load configuration
            self.config = config_manager.load_config()
            logger.info("✅ Configuration loaded successfully")
            
            # Print configuration summary
            self.print_config_summary()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Configuration validation failed: {e}")
            return False
    
    def print_config_summary(self) -> None:
        """Print a summary of the current configuration"""
        print("\n" + "="*60)
        print("📋 CONFIGURATION SUMMARY")
        print("="*60)
        print(f"Master List Method: {self.config.master_list_method}")
        print(f"Transcript Method: {self.config.transcript_method}")
        print(f"Channel URL: {self.config.channel_url}")
        print(f"Master File: {self.config.master_file}")
        print(f"Max Videos per Update: {self.config.max_videos_per_update}")
        
        # API Key status
        if self.config.youtube_api_key:
            print(f"YouTube API Key: {self.config.youtube_api_key[:10]}...")
        else:
            print("YouTube API Key: Not provided")
        
        # yt-dlp settings
        if self.config.ytdlp_cookies_file:
            print(f"yt-dlp Cookies File: {self.config.ytdlp_cookies_file}")
        else:
            print("yt-dlp Cookies File: Not specified")
        
        print(f"yt-dlp Use Proxy: {self.config.ytdlp_use_proxy}")
        
        # Proxy settings
        if self.config.webshare_proxy:
            print(f"Proxy: {self.config.webshare_proxy[:20]}...")
        else:
            print("Proxy: Not specified")
        
        print("="*60)
    
    def test_video_fetcher(self) -> bool:
        """Test the configured video fetcher"""
        logger.info("🔍 Testing video fetcher...")
        
        try:
            # Get fetcher configuration
            fetcher_config = config_manager.get_master_fetcher_config()
            
            # Create fetcher
            self.video_fetcher = VideoFetcherFactory.create_fetcher(fetcher_config)
            logger.info(f"✅ Video fetcher created successfully ({self.config.master_list_method})")
            
            # Test channel ID extraction
            logger.info("🔍 Testing channel ID extraction...")
            channel_id = self.video_fetcher.get_channel_id(self.config.channel_url)
            
            if channel_id:
                logger.info(f"✅ Channel ID extracted successfully: {channel_id}")
            else:
                logger.warning("⚠️ Could not extract channel ID")
                return False
            
            # Test video fetching (small number for testing)
            logger.info("🔍 Testing video fetching (limited to 5 videos)...")
            videos = self.video_fetcher.fetch_videos(self.config.channel_url, 5)
            
            if videos:
                logger.info(f"✅ Successfully fetched {len(videos)} test videos")
                logger.info(f"Sample video: {videos[0].get('title', 'Unknown')[:50]}...")
            else:
                logger.warning("⚠️ No videos fetched in test")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Video fetcher test failed: {e}")
            return False
    
    def test_transcript_downloader(self) -> bool:
        """Test the configured transcript downloader"""
        logger.info("🔍 Testing transcript downloader...")
        
        try:
            # Get transcript configuration
            transcript_config = config_manager.get_transcript_downloader_config()
            
            # Create downloader
            self.transcript_downloader = TranscriptDownloaderFactory.create_downloader(transcript_config)
            logger.info(f"✅ Transcript downloader created successfully ({self.config.transcript_method})")
            
            # Test with a sample video (use a known video ID)
            test_video_id = "dQw4w9WgXcQ"  # Rick Roll - known to have transcripts
            test_video_url = f"https://www.youtube.com/watch?v={test_video_id}"
            
            logger.info(f"🔍 Testing transcript availability check for {test_video_id}...")
            available = self.transcript_downloader.is_transcript_available(test_video_id, test_video_url)
            
            if available:
                logger.info("✅ Transcript availability check successful")
            else:
                logger.info("ℹ️ No transcript available for test video (this is normal)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Transcript downloader test failed: {e}")
            return False
    
    def test_file_permissions(self) -> bool:
        """Test file permissions and directory access"""
        logger.info("🔍 Testing file permissions...")
        
        try:
            # Test master file directory
            master_dir = os.path.dirname(self.config.master_file)
            if not os.path.exists(master_dir):
                os.makedirs(master_dir, exist_ok=True)
                logger.info(f"✅ Created master file directory: {master_dir}")
            
            # Test transcript directory
            transcript_dir = "data/transcripts"
            if not os.path.exists(transcript_dir):
                os.makedirs(transcript_dir, exist_ok=True)
                logger.info(f"✅ Created transcript directory: {transcript_dir}")
            
            # Test log directory
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
                logger.info(f"✅ Created log directory: {log_dir}")
            
            # Test write permissions
            test_file = os.path.join(master_dir, "test_write.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            logger.info("✅ Write permissions test passed")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ File permissions test failed: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all validation tests"""
        logger.info("🚀 Starting configuration validation tests...")
        
        tests = [
            ("Configuration Loading", self.validate_configuration),
            ("File Permissions", self.test_file_permissions),
            ("Video Fetcher", self.test_video_fetcher),
            ("Transcript Downloader", self.test_transcript_downloader)
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*50}")
            logger.info(f"Running test: {test_name}")
            logger.info(f"{'='*50}")
            
            try:
                result = test_func()
                results[test_name] = result
                
                if result:
                    logger.info(f"✅ {test_name} test passed")
                else:
                    logger.error(f"❌ {test_name} test failed")
                    
            except Exception as e:
                logger.error(f"❌ {test_name} test failed with exception: {e}")
                results[test_name] = False
        
        # Print summary
        self.print_test_summary(results)
        
        # Return overall result
        return all(results.values())
    
    def print_test_summary(self, results: Dict[str, bool]) -> None:
        """Print test results summary"""
        print("\n" + "="*60)
        print("📊 VALIDATION TEST RESULTS")
        print("="*60)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name:<25} {status}")
        
        print("="*60)
        
        if all(results.values()):
            print("🎉 All tests passed! Configuration is valid.")
        else:
            print("⚠️ Some tests failed. Please check the configuration.")
        
        print("="*60)

def main():
    """Main entry point"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    try:
        validator = ConfigValidator()
        success = validator.run_all_tests()
        
        if success:
            print("\n✅ Configuration validation completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Configuration validation failed!")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"❌ Fatal error during validation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()