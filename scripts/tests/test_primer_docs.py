"""The primers in docs/primer name many files; fail when one is renamed or removed so the docs do not rot."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIMERS = sorted((ROOT / "docs" / "primer").glob("*.md"))
# paths that are examples or git-ignored output, not files that must exist
ALLOWED_MISSING = ("sdks/bing", "data/transcripts")
PATH = re.compile(r"`((?:sdks|apps|scripts|docs|data)/[A-Za-z0-9_./-]+)`")
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def test_there_are_primers():
    assert PRIMERS, "docs/primer has no .md files"


def test_paths_named_in_primers_exist():
    missing = []
    for doc in PRIMERS:
        for path in PATH.findall(doc.read_text()):
            if path.startswith(ALLOWED_MISSING) or "..." in path:
                continue
            if not (ROOT / path).exists():
                missing.append(f"{doc.name}: {path}")
    assert not missing, "primers name files that do not exist:\n" + "\n".join(missing)


def test_links_between_docs_resolve():
    broken = []
    for doc in PRIMERS:
        for target in LINK.findall(doc.read_text()):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (doc.parent / target).resolve().exists():
                broken.append(f"{doc.name}: {target}")
    assert not broken, "broken links in primers:\n" + "\n".join(broken)
