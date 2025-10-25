#!/usr/bin/env python3
"""
Demo Script for Configurable Video System

This script demonstrates the configurable video fetching and transcript downloading system.
It shows how to use different configurations and methods.
"""

import os
import sys
import logging
from datetime import datetime

# Import our configurable modules
from config_manager import config_manager
from video_fetchers import VideoFetcherFactory
from transcript_downloaders import TranscriptDownloaderFactory, TranscriptManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/demo_configurable_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def demo_configuration():
    """Demonstrate configuration loading and validation"""
    print("\n" + "="*60)
    print("🔧 CONFIGURATION DEMO")
    print("="*60)
    
    try:
        # Load configuration
        config = config_manager.load_config()
        
        print(f"✅ Configuration loaded successfully")
        print(f"📋 Master List Method: {config.master_list_method}")
        print(f"📋 Transcript Method: {config.transcript_method}")
        print(f"📋 Channel URL: {config.channel_url}")
        print(f"📋 Master File: {config.master_file}")
        
        # Show proxy configuration
        if config.webshare_proxy_username and config.webshare_proxy_password:
            print(f"🔧 Webshare Proxy: {config.webshare_proxy_username}@proxy.webshare.io:80")
        elif config.webshare_proxy:
            print(f"🔧 Custom Proxy: {config.webshare_proxy[:20]}...")
        else:
            print("🔧 Proxy: Not configured")
        
        # Show fetcher configuration
        fetcher_config = config_manager.get_master_fetcher_config()
        print(f"🔧 Fetcher Config: {fetcher_config}")
        
        # Show transcript configuration
        transcript_config = config_manager.get_transcript_downloader_config()
        print(f"🔧 Transcript Config: {transcript_config}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration demo failed: {e}")
        return False

def demo_video_fetcher():
    """Demonstrate video fetcher creation and basic functionality"""
    print("\n" + "="*60)
    print("📺 VIDEO FETCHER DEMO")
    print("="*60)
    
    try:
        # Get fetcher configuration
        fetcher_config = config_manager.get_master_fetcher_config()
        
        # Create fetcher
        fetcher = VideoFetcherFactory.create_fetcher(fetcher_config)
        print(f"✅ Video fetcher created: {type(fetcher).__name__}")
        
        # Test channel ID extraction (this might fail due to YouTube restrictions)
        print("🔍 Testing channel ID extraction...")
        try:
            channel_id = fetcher.get_channel_id("https://www.youtube.com/@AdamSeekerOfficial")
            if channel_id:
                print(f"✅ Channel ID extracted: {channel_id}")
            else:
                print("⚠️ Could not extract channel ID (may require authentication)")
        except Exception as e:
            print(f"⚠️ Channel ID extraction failed (expected): {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Video fetcher demo failed: {e}")
        return False

def demo_transcript_downloader():
    """Demonstrate transcript downloader creation and basic functionality"""
    print("\n" + "="*60)
    print("📝 TRANSCRIPT DOWNLOADER DEMO")
    print("="*60)
    
    try:
        # Get transcript configuration
        transcript_config = config_manager.get_transcript_downloader_config()
        
        # Create downloader
        downloader = TranscriptDownloaderFactory.create_downloader(transcript_config)
        print(f"✅ Transcript downloader created: {type(downloader).__name__}")
        
        # Test transcript availability check
        print("🔍 Testing transcript availability check...")
        test_video_id = "dQw4w9WgXcQ"  # Rick Roll - known to have transcripts
        test_video_url = f"https://www.youtube.com/watch?v={test_video_id}"
        
        try:
            available = downloader.is_transcript_available(test_video_id, test_video_url)
            if available:
                print(f"✅ Transcript available for test video")
            else:
                print(f"ℹ️ No transcript available for test video")
        except Exception as e:
            print(f"⚠️ Transcript availability check failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Transcript downloader demo failed: {e}")
        return False

def demo_transcript_manager():
    """Demonstrate transcript manager functionality"""
    print("\n" + "="*60)
    print("📊 TRANSCRIPT MANAGER DEMO")
    print("="*60)
    
    try:
        # Create transcript manager
        config = config_manager.load_config()
        manager = TranscriptManager(config.master_file)
        
        # Get transcript statistics
        stats = manager.get_transcript_stats()
        print(f"📊 Transcript Statistics:")
        print(f"  Total Videos: {stats['total_videos']}")
        print(f"  Videos with Transcripts: {stats['videos_with_transcripts']}")
        print(f"  Transcript Files Exist: {stats['transcript_files_exist']}")
        print(f"  Videos without Transcripts: {stats['videos_without_transcripts']}")
        
        # Get videos without transcripts
        videos_without = manager.get_videos_without_transcripts()
        print(f"📝 Videos without transcripts: {len(videos_without)}")
        
        if videos_without:
            print("  Sample videos without transcripts:")
            for i, video in enumerate(videos_without[:3], 1):
                title = video.get('title', 'Unknown Title')
                video_id = video.get('video_id', 'Unknown ID')
                print(f"    {i}. {title[:50]}... ({video_id})")
        
        return True
        
    except Exception as e:
        print(f"❌ Transcript manager demo failed: {e}")
        return False

def demo_error_handling():
    """Demonstrate error handling with invalid configurations"""
    print("\n" + "="*60)
    print("⚠️ ERROR HANDLING DEMO")
    print("="*60)
    
    print("🔍 Testing error handling with invalid configurations...")
    
    # Test invalid master list method
    try:
        from video_fetchers import VideoFetcherFactory
        invalid_config = {'method': 'invalid_method'}
        VideoFetcherFactory.create_fetcher(invalid_config)
        print("❌ Should have failed with invalid method")
    except ValueError as e:
        print(f"✅ Correctly caught invalid method error: {e}")
    
    # Test invalid transcript method
    try:
        from transcript_downloaders import TranscriptDownloaderFactory
        invalid_config = {'method': 'invalid_method'}
        TranscriptDownloaderFactory.create_downloader(invalid_config)
        print("❌ Should have failed with invalid method")
    except ValueError as e:
        print(f"✅ Correctly caught invalid transcript method error: {e}")
    
    # Test missing API key for YouTube API method
    try:
        invalid_config = {'method': 'youtube_api'}  # No API key
        VideoFetcherFactory.create_fetcher(invalid_config)
        print("❌ Should have failed with missing API key")
    except ValueError as e:
        print(f"✅ Correctly caught missing API key error: {e}")
    
    return True

def main():
    """Main demo function"""
    print("🚀 CONFIGURABLE VIDEO SYSTEM DEMO")
    print("="*60)
    print("This demo shows the configurable video fetching and transcript downloading system.")
    print("The system has NO automatic fallbacks - it uses your configured method or fails clearly.")
    print("="*60)
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    demos = [
        ("Configuration Loading", demo_configuration),
        ("Video Fetcher", demo_video_fetcher),
        ("Transcript Downloader", demo_transcript_downloader),
        ("Transcript Manager", demo_transcript_manager),
        ("Error Handling", demo_error_handling)
    ]
    
    results = {}
    
    for demo_name, demo_func in demos:
        print(f"\n{'='*60}")
        print(f"Running demo: {demo_name}")
        print(f"{'='*60}")
        
        try:
            result = demo_func()
            results[demo_name] = result
            
            if result:
                print(f"✅ {demo_name} demo completed successfully")
            else:
                print(f"❌ {demo_name} demo failed")
                
        except Exception as e:
            print(f"❌ {demo_name} demo failed with exception: {e}")
            results[demo_name] = False
    
    # Print summary
    print("\n" + "="*60)
    print("📊 DEMO RESULTS SUMMARY")
    print("="*60)
    
    for demo_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{demo_name:<25} {status}")
    
    print("="*60)
    
    if all(results.values()):
        print("🎉 All demos completed successfully!")
        print("\n📋 Next steps:")
        print("1. Configure your preferred methods in config.env")
        print("2. Run: python3 scripts/validate_config.py")
        print("3. Use the configurable scripts:")
        print("   - python3 scripts/update_master_configurable.py")
        print("   - python3 scripts/rebuild_master_configurable.py")
        print("   - python3 scripts/manage_transcripts.py")
    else:
        print("⚠️ Some demos failed. Check the configuration and try again.")
    
    print("="*60)

if __name__ == "__main__":
    main()