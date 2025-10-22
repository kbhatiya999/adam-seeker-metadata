#!/usr/bin/env python3
"""
Video Management Utility Script

This script provides utilities for manually managing the video list:
- Categorize uncategorized videos
- Set relevance scores
- Add notes and tags
- Generate reports
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import argparse

class VideoManager:
    def __init__(self, master_file: str):
        self.master_file = master_file
        
    def load_master_list(self) -> Dict:
        """Load the current master video list"""
        try:
            with open(self.master_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Master file {self.master_file} not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            sys.exit(1)
    
    def save_master_list(self, data: Dict) -> None:
        """Save the updated master video list"""
        try:
            with open(self.master_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("✅ Master list updated successfully")
        except Exception as e:
            print(f"❌ Error saving master list: {e}")
            sys.exit(1)
    
    def list_uncategorized(self) -> List[Dict]:
        """List all uncategorized videos"""
        master_data = self.load_master_list()
        uncategorized = [
            video for video in master_data.get('videos', [])
            if video.get('status') == 'uncategorized'
        ]
        return uncategorized
    
    def categorize_video(self, video_id: str, categories: List[str], 
                        relevance_score: int = None, notes: str = "") -> bool:
        """Categorize a video and set its properties"""
        master_data = self.load_master_list()
        
        for video in master_data.get('videos', []):
            if video['video_id'] == video_id:
                video['categories'] = categories
                video['status'] = 'categorized'
                video['needs_review'] = False
                video['last_checked'] = datetime.now().isoformat()[:10]
                
                if relevance_score is not None:
                    video['relevance_score'] = relevance_score
                if notes:
                    video['notes'] = notes
                
                self.save_master_list(master_data)
                print(f"✅ Video {video_id} categorized successfully")
                return True
        
        print(f"❌ Video {video_id} not found")
        return False
    
    def mark_priority(self, video_id: str, category: str, relevance_score: int = 10) -> bool:
        """Mark a video as priority and immediately categorize it"""
        return self.categorize_video(video_id, [category], relevance_score, "Priority video")
    
    def generate_report(self) -> None:
        """Generate a comprehensive report of the video list"""
        master_data = self.load_master_list()
        videos = master_data.get('videos', [])
        
        print("\n" + "="*60)
        print("📊 VIDEO LIST REPORT")
        print("="*60)
        print(f"Total Videos: {len(videos)}")
        print(f"Last Updated: {master_data.get('last_updated', 'Never')}")
        print(f"Channel: {master_data.get('channel_url', 'Unknown')}")
        
        # Status breakdown
        status_counts = {}
        for video in videos:
            status = video.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"\n📈 Status Breakdown:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
        
        # Category breakdown
        category_counts = {}
        for video in videos:
            for category in video.get('categories', []):
                category_counts[category] = category_counts.get(category, 0) + 1
        
        if category_counts:
            print(f"\n🏷️  Category Breakdown:")
            for category, count in sorted(category_counts.items()):
                print(f"  {category}: {count}")
        
        # Relevance score distribution
        relevance_scores = [v.get('relevance_score') for v in videos if v.get('relevance_score')]
        if relevance_scores:
            avg_score = sum(relevance_scores) / len(relevance_scores)
            print(f"\n⭐ Relevance Scores:")
            print(f"  Average: {avg_score:.1f}")
            print(f"  Scored videos: {len(relevance_scores)}/{len(videos)}")
        
        # Recent videos
        recent_videos = sorted(videos, key=lambda x: x.get('upload_date', ''), reverse=True)[:5]
        print(f"\n🆕 Recent Videos:")
        for video in recent_videos:
            status_emoji = "✅" if video.get('status') == 'categorized' else "⏳"
            print(f"  {status_emoji} {video.get('title', 'Unknown')[:50]}... ({video.get('upload_date', 'Unknown')})")
        
        print("="*60)
    
    def interactive_categorize(self) -> None:
        """Interactive mode for categorizing videos"""
        uncategorized = self.list_uncategorized()
        
        if not uncategorized:
            print("✅ No uncategorized videos found!")
            return
        
        print(f"\n📝 Found {len(uncategorized)} uncategorized videos:")
        print("-" * 80)
        
        for i, video in enumerate(uncategorized, 1):
            print(f"\n{i}. {video.get('title', 'Unknown Title')}")
            print(f"   ID: {video.get('video_id')}")
            print(f"   Date: {video.get('upload_date', 'Unknown')}")
            print(f"   URL: {video.get('url', 'Unknown')}")
            print(f"   Description: {video.get('description', 'No description')[:100]}...")
            
            # Get user input
            print("\nOptions:")
            print("  [c]ategorize  [s]kip  [q]uit")
            choice = input("Choice: ").lower().strip()
            
            if choice == 'q':
                break
            elif choice == 's':
                continue
            elif choice == 'c':
                categories_input = input("Categories (comma-separated): ").strip()
                categories = [cat.strip() for cat in categories_input.split(',') if cat.strip()]
                
                relevance_input = input("Relevance score (1-10, optional): ").strip()
                relevance_score = None
                if relevance_input.isdigit():
                    relevance_score = int(relevance_input)
                
                notes = input("Notes (optional): ").strip()
                
                if categories:
                    self.categorize_video(video['video_id'], categories, relevance_score, notes)
                else:
                    print("❌ No categories provided, skipping...")

def main():
    parser = argparse.ArgumentParser(description='Manage video list')
    parser.add_argument('--master-file', default='data/videos_master.json',
                       help='Path to master video list file')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List uncategorized videos
    subparsers.add_parser('list-uncategorized', help='List uncategorized videos')
    
    # Categorize a specific video
    categorize_parser = subparsers.add_parser('categorize', help='Categorize a video')
    categorize_parser.add_argument('video_id', help='Video ID to categorize')
    categorize_parser.add_argument('--categories', required=True, 
                                 help='Comma-separated list of categories')
    categorize_parser.add_argument('--relevance', type=int, choices=range(1, 11),
                                 help='Relevance score (1-10)')
    categorize_parser.add_argument('--notes', help='Notes about the video')
    
    # Mark as priority
    priority_parser = subparsers.add_parser('priority', help='Mark video as priority')
    priority_parser.add_argument('video_id', help='Video ID to mark as priority')
    priority_parser.add_argument('--category', required=True, help='Category for priority video')
    priority_parser.add_argument('--relevance', type=int, default=10, choices=range(1, 11),
                                help='Relevance score (default: 10)')
    
    # Generate report
    subparsers.add_parser('report', help='Generate video list report')
    
    # Interactive mode
    subparsers.add_parser('interactive', help='Interactive categorization mode')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = VideoManager(args.master_file)
    
    if args.command == 'list-uncategorized':
        uncategorized = manager.list_uncategorized()
        if uncategorized:
            print(f"\n📝 Found {len(uncategorized)} uncategorized videos:")
            for video in uncategorized:
                print(f"  • {video.get('title', 'Unknown')} ({video.get('video_id')})")
        else:
            print("✅ No uncategorized videos found!")
    
    elif args.command == 'categorize':
        categories = [cat.strip() for cat in args.categories.split(',')]
        manager.categorize_video(args.video_id, categories, args.relevance, args.notes)
    
    elif args.command == 'priority':
        manager.mark_priority(args.video_id, args.category, args.relevance)
    
    elif args.command == 'report':
        manager.generate_report()
    
    elif args.command == 'interactive':
        manager.interactive_categorize()

if __name__ == "__main__":
    main()
