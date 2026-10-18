"""The READMEs are the way in for new people: fail when one names a mise task, a file or a section that does not exist."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READMES = sorted(ROOT.glob("README*.md"))
TASKS = set(tomllib.loads((ROOT / "mise.toml").read_text())["tasks"])
# git-ignored output and examples, not files that must exist in a fresh clone
ALLOWED_MISSING = ("data/transcripts", "data/llm", "data/knowledge", "data/eval", "data/videos_master.json.backup_",
                   "logs/transcripts.log", "sdks/rag")
TASK = re.compile(r"mise run ([a-z][A-Za-z0-9:_.-]*)")
PATH = re.compile(r"`((?:sdks|apps|scripts|docs|data|eval|logs|\.github)/[A-Za-z0-9_./-]*)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def slug(heading: str) -> str:
    """GitHub's anchor for a heading: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"`", "", heading.strip().lower())
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(doc: Path) -> set:
    text = re.sub(r"```.*?```", "", doc.read_text(), flags=re.DOTALL)  # '# comments' in code are not headings
    return {slug(h) for h in HEADING.findall(text)}


def test_there_are_readmes():
    assert (ROOT / "README.md") in READMES


def test_tasks_named_in_readmes_exist():
    missing = [f"{doc.name}: mise run {task}" for doc in READMES for task in TASK.findall(doc.read_text())
               if task not in TASKS]
    assert not missing, "READMEs name mise tasks that do not exist:\n" + "\n".join(missing)


def test_paths_named_in_readmes_exist():
    missing = []
    for doc in READMES:
        for path in PATH.findall(doc.read_text()):
            if path.startswith(ALLOWED_MISSING) or "..." in path:
                continue
            if not (ROOT / path).exists():
                missing.append(f"{doc.name}: {path}")
    assert not missing, "READMEs name files that do not exist:\n" + "\n".join(missing)


def test_links_and_anchors_resolve():
    broken = []
    for doc in READMES:
        for target in LINK.findall(doc.read_text()):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            file, _, anchor = target.partition("#")
            path = (doc.parent / file).resolve() if file else doc
            if not path.exists():
                broken.append(f"{doc.name}: {target}")
            elif anchor and path.suffix == ".md" and anchor not in anchors(path):
                broken.append(f"{doc.name}: {target} (no such heading)")
    assert not broken, "broken links in READMEs:\n" + "\n".join(broken)


def test_slug_matches_github():
    assert slug("Set it up on your own copy (a fork)") == "set-it-up-on-your-own-copy-a-fork"
    assert slug("Step 2: get the code") == "step-2-get-the-code"
    assert slug("Keys (optional)") == "keys-optional"
