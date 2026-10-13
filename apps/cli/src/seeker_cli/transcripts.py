"""`seeker transcripts ...`: download and compare transcripts (explicit method, no fallback)."""

import logging
import os
import sys

from seeker_sdk_core import DEFAULT_MASTER_FILE, ConfigError, MasterList, SeekerError, TranscriptError, env
from seeker_sdk_transcripts import (FINAL_FORMATS, SOURCE_FORMATS, Network, TranscriptConfig, compare, diff_outcomes,
                                    download_many, get_method, method_names, parse_finals)
from seeker_sdk_transcripts.service import DEFAULT_OUT_DIR

logger = logging.getLogger("seeker.transcripts")


def add_parser(sub) -> None:
    p = sub.add_parser("transcripts", help="download and compare transcripts")
    p.add_argument("--master-file", default=DEFAULT_MASTER_FILE)
    p.add_argument("--method", help=f"transcript method (or TRANSCRIPT_METHOD): {', '.join(method_names())}")
    p.add_argument("--format", choices=SOURCE_FORMATS,
                   help="format DOWNLOADED from YouTube by either method (or TRANSCRIPT_FORMAT; default ttml)")
    p.add_argument("--final", help=f"FINAL formats, comma separated from {','.join(FINAL_FORMATS)} "
                                   "(or TRANSCRIPT_FINAL; default srt,txt)")
    p.add_argument("--keep-source", action="store_true", help="also keep the downloaded file")
    tsub = p.add_subparsers(dest="tcmd", required=True)
    tsub.add_parser("stats", help="show how many videos have transcripts")
    lm = tsub.add_parser("list-missing", help="list videos without a transcript")
    lm.add_argument("--limit", type=int, default=20)
    dm = tsub.add_parser("download-missing", help="download transcripts for videos that lack one")
    dm.add_argument("--limit", type=int, default=10, help="max videos this run (default 10)")
    d1 = tsub.add_parser("download", help="download the transcript for one video")
    d1.add_argument("video_id")
    c1 = tsub.add_parser("check", help="check whether a transcript is available for one video")
    c1.add_argument("video_id")
    cp = tsub.add_parser("compare", help="download one video with ALL methods side by side (nothing is linked)")
    cp.add_argument("video_id")
    p.set_defaults(func=run)


def _config(args) -> TranscriptConfig:
    finals = parse_finals(args.final or env("TRANSCRIPT_FINAL") or "srt,txt")
    net = Network(
        cookies_file=env("YTDLP_COOKIES_FILE"),
        proxy=env("PROXY_URL"),
        webshare_username=env("WEBSHARE_PROXY_USERNAME"),
        webshare_password=env("WEBSHARE_PROXY_PASSWORD"),
    )
    try:
        return TranscriptConfig(source_format=args.format or env("TRANSCRIPT_FORMAT") or "ttml",
                                finals=finals, keep_source=args.keep_source, network=net)
    except ConfigError as e:
        sys.exit(str(e))


def _method_name(args) -> str:
    name = args.method or env("TRANSCRIPT_METHOD")
    if name not in method_names():
        sys.exit(f"Choose a method with --method or TRANSCRIPT_METHOD: one of {', '.join(method_names())} "
                 f"(got {name!r}). There is no default and no fallback.")
    return name


def run(args) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    try:
        master = MasterList.load_strict(args.master_file)
    except SeekerError as e:
        sys.exit(str(e))

    if args.tcmd == "stats":
        total = len(master.videos)
        missing = len(master.videos_without_transcript())
        print(f"Videos: {total}  with transcript: {total - missing}  missing: {missing}")
        return 0
    if args.tcmd == "list-missing":
        for v in master.videos_without_transcript()[:args.limit]:
            print(f"{v['video_id']}  {v.get('upload_date', '')}  {v.get('title', '')[:70]}")
        return 0

    config = _config(args)
    if args.tcmd == "compare":
        return _compare(args.video_id, config)

    name = _method_name(args)
    method = get_method(name, config)
    logger.info("Method: %s (no fallback); download format: %s; final: %s",
                name, config.source_format, ",".join(config.finals))

    if args.tcmd == "check":
        try:
            print("available" if method.check(args.video_id) else "not available")
        except TranscriptError as e:
            sys.exit(str(e))
        return 0

    ids = [args.video_id] if args.tcmd == "download" else \
        [v["video_id"] for v in master.videos_without_transcript()[:args.limit]]
    result = download_many(method, master, ids)
    print(f"Done: {result.ok} downloaded, {result.failed} failed/unavailable")
    return 0 if result.failed == 0 else 1


def _compare(video_id: str, config: TranscriptConfig) -> int:
    names = method_names()
    outcomes = compare(video_id, config, names)
    print(f"\nCompare for {video_id}  (downloaded as {config.source_format}, final: {','.join(config.finals)})")
    for o in outcomes:
        if o.status == "ok":
            primary = next(iter(o.files))
            print(f"  {o.method:<24} ok      {o.size_kb} KB {primary}  {o.words} words")
            for ext, path in o.files.items():
                print(f"  {'':<24}         {ext}: {path}")
        else:
            print(f"  {o.method:<24} {o.status.upper() if o.status == 'failed' else o.status:<7} {o.detail}")
    ok = [o for o in outcomes if o.status == "ok"]
    if len(ok) == len(outcomes) and len(ok) >= 2:
        first, second = ok[0], ok[1]
        print(f"\n  Diff of the final files ({first.method} vs {second.method}):")
        for d in diff_outcomes(first, second):
            if d.identical:
                same = open(first.files[d.ext], "rb").read() == open(second.files[d.ext], "rb").read()
                print(f"    {d.ext}: identical ({d.lines_a} lines, byte for byte: {same})")
            else:
                print(f"    {d.ext}: DIFFERENT, {len(d.changed)} changed lines ({d.lines_a} vs {d.lines_b} lines)")
                for line in d.changed[:6]:
                    print("      " + line[:110])
    return 0 if len(ok) == len(outcomes) else 1
