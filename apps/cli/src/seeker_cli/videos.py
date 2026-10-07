"""`seeker videos ...`: update, rebuild and manage the master video list."""

import argparse
import logging
import sys

from seeker_sdk_core import DEFAULT_CHANNEL_URL, DEFAULT_MASTER_FILE, ConfigError, MasterList, env
from seeker_sdk_core.logs import setup_logging
from seeker_sdk_videos import catalog, describe, make_source, rebuild, resolve_method, update

logger = logging.getLogger("seeker.videos")


def add_parser(sub) -> None:
    videos = sub.add_parser("videos", help="update, rebuild and manage the video list")
    vsub = videos.add_subparsers(dest="videos_cmd", required=True)

    up = vsub.add_parser("update", help="add new videos to the master list")
    up.add_argument("--rebuild", action="store_true", help="rebuild from scratch instead (same as `videos rebuild`)")
    up.add_argument("--master-file", default=DEFAULT_MASTER_FILE)
    up.add_argument("--channel-url", default=DEFAULT_CHANNEL_URL)
    up.add_argument("--force", action="store_true", help="skip the confirmation prompt (with --rebuild)")
    up.set_defaults(func=cmd_update)

    rb = vsub.add_parser("rebuild", help="rebuild the master list from YouTube (keeps manual work)")
    rb.add_argument("--master-file", default=DEFAULT_MASTER_FILE)
    rb.add_argument("--channel-url", default=DEFAULT_CHANNEL_URL)
    rb.add_argument("--no-preserve", action="store_true", help="do not preserve manual categorizations")
    rb.add_argument("--force", action="store_true", help="skip the confirmation prompt")
    rb.set_defaults(func=cmd_rebuild)

    mg = vsub.add_parser("manage", help="categorize videos, set priorities, report")
    mg.add_argument("--master-file", default=DEFAULT_MASTER_FILE)
    msub = mg.add_subparsers(dest="command")
    msub.add_parser("list-uncategorized", help="list uncategorized videos")
    cat = msub.add_parser("categorize", help="categorize a video")
    cat.add_argument("video_id")
    cat.add_argument("--categories", required=True, help="comma-separated list of categories")
    cat.add_argument("--relevance", type=int, choices=range(1, 11), help="relevance score (1-10)")
    cat.add_argument("--notes", help="notes about the video")
    pri = msub.add_parser("priority", help="mark a video as priority")
    pri.add_argument("video_id")
    pri.add_argument("--category", required=True, help="category for the priority video")
    pri.add_argument("--relevance", type=int, default=10, choices=range(1, 11), help="relevance score (default 10)")
    msub.add_parser("report", help="generate the video list report")
    msub.add_parser("interactive", help="interactive categorization")
    mg.set_defaults(func=cmd_manage, manage_parser=mg)


def _source_for(args):
    api_key = env("YOUTUBE_API_KEY")
    try:
        choice = resolve_method(api_key)
    except ConfigError as e:
        sys.exit(str(e))
    describe(choice, api_key)
    return choice, make_source(choice, api_key, args.channel_url)


def cmd_update(args) -> int:
    setup_logging("logs/update_master.log")
    if args.rebuild:
        logger.info("🔄 Rebuild mode requested - running the rebuild")
        args.no_preserve = False
        return cmd_rebuild(args)

    choice, source = _source_for(args)
    try:
        result = update(args.master_file, args.channel_url, source)
    except Exception as e:
        if not choice.explicit:
            raise
        logger.error(f"❌ Update failed with method {choice.name}: {e}")
        sys.exit(1)

    if result.updated:
        logger.info(f"✅ Successfully added {len(result.new_videos)} new videos")
        logger.info(f"📊 Total videos in master list: {result.total_videos}")
        for video in result.new_videos:  # the workflow reads these lines for the notification issue
            logger.info(f"🆕 New: {video['title']} ({video['upload_date']})")
    else:
        logger.info("ℹ️ No new videos found")
    return 0


def confirm_rebuild() -> bool:
    print("\n" + "=" * 60)
    print("⚠️  WARNING: MASTER LIST REBUILD")
    print("=" * 60)
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
    print("❌ Videos that are no longer public on YouTube")
    print("=" * 60)
    while True:
        response = input("\nAre you sure you want to proceed? (yes/no): ").lower().strip()
        if response in ("yes", "y"):
            return True
        if response in ("no", "n"):
            return False
        print("Please enter 'yes' or 'no'")


def cmd_rebuild(args) -> int:
    setup_logging("logs/rebuild_master.log")
    if not args.force and not confirm_rebuild():
        print("❌ Rebuild cancelled by user")
        return 0

    choice, source = _source_for(args)
    backup = MasterList(args.master_file).timestamped_backup()
    try:
        result = rebuild(args.master_file, args.channel_url, source, preserve_manual=not args.no_preserve)
    except Exception as e:
        if not choice.explicit:
            raise
        logger.error(f"❌ Rebuild failed with method {choice.name}: {e}")
        sys.exit(1)

    if result.success:
        logger.info("🎉 Rebuild completed successfully!")
        logger.info(f"📊 Total videos: {result.total_videos}")
        logger.info(f"🔄 Preserved manual data: {result.preserved_manual}")
        if backup:
            logger.info(f"📦 Backup available: {backup}")
    else:
        logger.error(f"❌ Rebuild failed: {result.error or 'Unknown error'}")
        if backup:
            logger.info(f"📦 Backup available for recovery: {backup}")
    return 0


def _load(path: str) -> MasterList:
    try:
        return MasterList.load_strict(path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_manage(args) -> int:
    if not args.command:
        args.manage_parser.print_help()
        return 0
    master = _load(args.master_file)

    def save() -> None:
        master.write(sort=False)
        print("✅ Master list updated successfully")

    if args.command == "list-uncategorized":
        items = catalog.list_uncategorized(master)
        if items:
            print(f"\n📝 Found {len(items)} uncategorized videos:")
            for video in items:
                print(f"  • {video.get('title', 'Unknown')} ({video.get('video_id')})")
        else:
            print("✅ No uncategorized videos found!")
    elif args.command == "categorize":
        categories = [c.strip() for c in args.categories.split(",")]
        _categorize(master, save, args.video_id, categories, args.relevance, args.notes or "")
    elif args.command == "priority":
        if catalog.mark_priority(master, args.video_id, args.category, args.relevance):
            save()
            print(f"✅ Video {args.video_id} categorized successfully")
        else:
            print(f"❌ Video {args.video_id} not found")
    elif args.command == "report":
        _print_report(catalog.report(master))
    elif args.command == "interactive":
        _interactive(master, save)
    return 0


def _categorize(master, save, video_id, categories, relevance, notes) -> None:
    if catalog.categorize(master, video_id, categories, relevance, notes):
        save()
        print(f"✅ Video {video_id} categorized successfully")
    else:
        print(f"❌ Video {video_id} not found")


def _print_report(r) -> None:
    print("\n" + "=" * 60)
    print("📊 VIDEO LIST REPORT")
    print("=" * 60)
    print(f"Total Videos: {r['total']}")
    print(f"Last Updated: {r['last_updated']}")
    print(f"Channel: {r['channel_url']}")
    print("\n📈 Status Breakdown:")
    for status, count in r["status_counts"].items():
        print(f"  {status}: {count}")
    if r["category_counts"]:
        print("\n🏷️  Category Breakdown:")
        for category, count in r["category_counts"].items():
            print(f"  {category}: {count}")
    if r["relevance_average"] is not None:
        print("\n⭐ Relevance Scores:")
        print(f"  Average: {r['relevance_average']:.1f}")
        print(f"  Scored videos: {r['scored']}/{r['total']}")
    print("\n🆕 Recent Videos:")
    for video in r["recent"]:
        emoji = "✅" if video.get("status") == "categorized" else "⏳"
        print(f"  {emoji} {video.get('title', 'Unknown')[:50]}... ({video.get('upload_date', 'Unknown')})")
    print("=" * 60)


def _interactive(master, save) -> None:
    items = catalog.list_uncategorized(master)
    if not items:
        print("✅ No uncategorized videos found!")
        return
    print(f"\n📝 Found {len(items)} uncategorized videos:")
    print("-" * 80)
    for i, video in enumerate(items, 1):
        print(f"\n{i}. {video.get('title', 'Unknown Title')}")
        print(f"   ID: {video.get('video_id')}")
        print(f"   Date: {video.get('upload_date', 'Unknown')}")
        print(f"   URL: {video.get('url', 'Unknown')}")
        print(f"   Description: {video.get('description', 'No description')[:100]}...")
        print("\nOptions:")
        print("  [c]ategorize  [s]kip  [q]uit")
        choice = input("Choice: ").lower().strip()
        if choice == "q":
            break
        if choice == "s":
            continue
        if choice == "c":
            categories = [c.strip() for c in input("Categories (comma-separated): ").split(",") if c.strip()]
            relevance_input = input("Relevance score (1-10, optional): ").strip()
            relevance = int(relevance_input) if relevance_input.isdigit() else None
            notes = input("Notes (optional): ").strip()
            if categories:
                _categorize(master, save, video["video_id"], categories, relevance, notes)
            else:
                print("❌ No categories provided, skipping...")
