#!/usr/bin/env python3
"""Scaffold a new SDK in the workspace.

    uv run python scripts/new_sdk.py <name> [--plugin video_sources|transcript_methods]

Creates sdks/<name> (distribution `seeker-sdk-<name>`, import `seeker_sdk_<name>`), with a README, a
test and, with --plugin, a plugin skeleton registered through an entry point. The package is
registered in the root pyproject (uv sources) so `uv sync --all-packages` picks it up and
`mise run build:sdks` builds its wheel.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PLUGIN_SKELETONS = {
    "video_sources": ("seeker.video_sources", "sources", "MySource", '''\
"""A video source plugin: pick it with MASTER_LIST_METHOD={entry}."""

from typing import Any, Dict, List, Optional

from seeker_sdk_videos import VideoSource


class {cls}(VideoSource):
    name = "{entry}"
    requires_api_key = False
    discovery_label = "Using {entry} for video discovery"

    def channel_id(self, channel_url: str) -> Optional[str]:
        raise NotImplementedError

    def fetch_recent(self, channel_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        raise NotImplementedError  # return dicts shaped like seeker_sdk_core.new_video(...)

    def fetch_all(self, channel_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError
''', "seeker-sdk-videos"),
    "transcript_methods": ("seeker.transcript_methods", "methods", "MyMethod", '''\
"""A transcript method plugin: pick it with --method {entry}."""

from typing import Optional

from seeker_sdk_transcripts import TranscriptMethod


class {cls}(TranscriptMethod):
    name = "{entry}"

    def check(self, video_id: str) -> bool:
        raise NotImplementedError

    def download(self, video_id: str, out_dir: str) -> Optional[str]:
        # download in self.config.source_format, convert with seeker_sdk_transcripts.produce_finals(...),
        # return seeker_sdk_transcripts.primary_path(out_dir, video_id, self.config.finals)
        raise NotImplementedError
''', "seeker-sdk-transcripts"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="short name, e.g. rag (creates seeker-sdk-rag)")
    parser.add_argument("--plugin", choices=sorted(PLUGIN_SKELETONS), help="also create a plugin skeleton")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9-]*", args.name):
        sys.exit("name must be lowercase letters, digits and dashes, starting with a letter")
    dist = f"seeker-sdk-{args.name}"
    module = dist.replace("-", "_")
    folder = ROOT / "sdks" / args.name
    if folder.exists():
        sys.exit(f"{folder} already exists")

    deps = ['"seeker-sdk-core>=0.1.0"']
    sources = ['seeker-sdk-core = { workspace = true }']
    entry_block = ""
    skeleton_module = None
    if args.plugin:
        group, sub, cls, source, needs = PLUGIN_SKELETONS[args.plugin]
        deps.append(f'"{needs}>=0.1.0"')
        sources.append(f"{needs} = {{ workspace = true }}")
        entry = args.name.replace("-", "_")
        entry_block = f'\n[project.entry-points."{group}"]\n{entry} = "{module}.{sub}:{cls}"\n'
        skeleton_module = (sub, source.format(entry=entry, cls=cls))

    (folder / "src" / module).mkdir(parents=True)
    (folder / "tests").mkdir()
    (folder / "pyproject.toml").write_text(f'''[project]
name = "{dist}"
version = "0.1.0"
description = "Seeker SDK {args.name}"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    {(","+chr(10)+"    ").join(deps)},
]
{entry_block}
[tool.uv.sources]
{chr(10).join(sources)}

[build-system]
requires = ["uv_build>=0.11,<0.12"]
build-backend = "uv_build"
''')
    (folder / "README.md").write_text(f"# {dist}\n\nDescribe what this SDK does and show a short usage example.\n")
    (folder / "src" / module / "py.typed").write_text("")
    (folder / "src" / module / "__init__.py").write_text(f'"""Seeker SDK {args.name}."""\n\n__version__ = "0.1.0"\n')
    if skeleton_module:
        (folder / "src" / module / f"{skeleton_module[0]}.py").write_text(skeleton_module[1])
    (folder / "tests" / f"test_{args.name.replace('-', '_')}_smoke.py").write_text(
        f'import {module}\n\n\ndef test_imports():\n    assert {module}.__version__\n')

    root = ROOT / "pyproject.toml"
    text = root.read_text()
    marker = "[tool.uv.sources]\n"
    line = f"{dist} = {{ workspace = true }}\n"
    if line not in text:
        text = text.replace(marker, marker + line, 1)
        root.write_text(text)

    print(f"Created sdks/{args.name} ({dist}).")
    print("Next: uv sync --all-packages && uv run pytest && mise run build:sdks")
    if args.plugin:
        print(f"The plugin skeleton is registered under {PLUGIN_SKELETONS[args.plugin][0]}; implement it, then "
              f"`uv run seeker plugins` lists it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
