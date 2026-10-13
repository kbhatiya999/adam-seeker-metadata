"""Entry point of the `seeker` command."""

import argparse
import sys
from typing import List, Optional

from seeker_sdk_core import plugins

from . import transcripts, videos


def _plugins(args) -> int:
    for group in (plugins.VIDEO_SOURCES, plugins.TRANSCRIPT_METHODS):
        print(group)
        for name, origin in plugins.describe(group).items():
            print(f"  {name:<24} {origin}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seeker", description="Adam Seeker metadata tools")
    sub = parser.add_subparsers(dest="area", required=True)
    videos.add_parser(sub)
    transcripts.add_parser(sub)
    pl = sub.add_parser("plugins", help="list the installed plugins (video sources, transcript methods)")
    pl.set_defaults(func=_plugins)
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
