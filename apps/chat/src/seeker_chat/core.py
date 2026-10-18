"""The chat app's logic, without Chainlit, so it can be tested.

A *pair* is a processed store (data/knowledge/<strategy>@<version>, made by `seeker knowledge process`) plus a chat
strategy. Answers use the same strategies as `seeker ask` and `seeker eval`, run on Gemini with the user's own key.
"""

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

from seeker_sdk_chat import Answer, ask, chat_strategy_names, get_chat_strategy
from seeker_sdk_knowledge import KnowledgeStore, hms
from seeker_sdk_llm import Provider, ToolRunner, Waiting

KEY_ENV = "GEMINI_API_KEY"
KEY_URL = "https://aistudio.google.com/apikey"
MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
NAMES = {"english-notes": "English notes", "chunks": "Raw captions", "keyword": "keyword search",
         "multilingual": "multilingual search"}
NO_KEY = (f"Add your Gemini API key first: open the **key** settings of this chat and paste it. Create one at "
          f"{KEY_URL} (sign in, then \"Create API key\"). The key stays in this browser and is not saved on the server.")
NOTHING_PROCESSED = ("No videos are processed yet, so there is nothing to search. Download some transcripts and "
                     "process them first: `mise run local:transcripts:manage -- --method ytdlp download-missing "
                     "--limit 5`, then `mise run local:knowledge:manage -- process --strategy chunks` (no key needed; "
                     "`--strategy english-notes` gives better answers but uses a model). Then reload this page.")


def root() -> Path:
    """The repository the app reads (data/, eval/); set by the launcher, else the working directory."""
    return Path(os.environ.get("SEEKER_ROOT") or os.getcwd())


@dataclass(frozen=True)
class Pair:
    processing: str   # store folder, e.g. english-notes@v1
    chat: str         # chat strategy, e.g. keyword
    videos: Tuple[str, ...]
    scores: Tuple[str, ...] = ()   # e.g. ("83% (queue)",) from the latest evaluations

    @property
    def name(self) -> str:
        return f"{self.processing}+{self.chat}"

    @property
    def label(self) -> str:
        strategy = self.processing.split("@")[0]
        return f"{NAMES.get(strategy, strategy)} + {NAMES.get(self.chat, self.chat)}"

    @property
    def description(self) -> str:
        scored = f" Evaluation: {', '.join(self.scores)}." if self.scores else ""
        return (f"Searches {len(self.videos)} processed video(s) ({self.processing}) with {self.chat}; "
                f"answers cite the video and time.{scored}")


def _scores(root: Path) -> Dict[Tuple[str, str], List[str]]:
    out: Dict[Tuple[str, str], List[str]] = {}
    for f in sorted((root / "data" / "eval" / "latest").glob("*.json")):
        run = json.loads(f.read_text(encoding="utf-8"))
        summary = run.get("summary", {})
        score = summary.get("score")
        if score is not None:
            partial = f", {summary['done']} of {summary['questions']} questions" if summary.get("waiting") else ""
            out.setdefault((run["processing"], run["chat"].split("@")[0]), []).append(
                f"{score * 100:.0f}% ({run.get('provider') or '?'}{partial})")
    return out


def pairs(root: Path) -> List[Pair]:
    """Every processed store x every chat strategy; English notes + keyword first (the best so far)."""
    folder = root / "data" / "knowledge"
    stores = [p for p in folder.iterdir() if (p / "passages").is_dir()] if folder.exists() else []
    stores.sort(key=lambda p: (not p.name.startswith("english-notes"), p.name))
    scores = _scores(root)
    out = []
    for store in stores:
        videos = tuple(sorted(f.stem for f in (store / "passages").glob("*.jsonl")))
        if videos:
            out += [Pair(store.name, chat, videos, tuple(scores.get((store.name, chat), [])))
                    for chat in chat_strategy_names()]
    return out


def find(root: Path, name: Optional[str]) -> Optional[Pair]:
    found = pairs(root)
    return next((p for p in found if p.name == name), found[0] if found else None)


def starters(root: Path, pair: Pair, limit: int = 4) -> List[Tuple[str, str]]:
    """(label, question) from eval/questions for the videos this pair has processed."""
    out: List[Tuple[str, str]] = []
    for video in pair.videos:
        path = root / "eval" / "questions" / f"{video}.toml"
        if path.exists():
            for q in tomllib.loads(path.read_text(encoding="utf-8")).get("question", []):
                if q["type"] in ("reference", "argument"):
                    out.append((q["question"][:60] + ("..." if len(q["question"]) > 60 else ""), q["question"]))
                    break
    return out[:limit]


def make_provider(api_key: str, model: Optional[str] = None) -> Provider:
    from seeker_sdk_gemini import GeminiProvider
    return GeminiProvider(api_key=api_key, model=model)


def answer(question: str, pair: Pair, api_key: str, root: Path, model: Optional[str] = None,
           provider_factory: Callable[[str, Optional[str]], Provider] = make_provider
           ) -> Tuple[Union[Answer, Waiting], ToolRunner]:
    strategy, _, version = pair.processing.partition("@")
    store = KnowledgeStore(str(root / "data" / "knowledge"), strategy, version)
    runner = ToolRunner(provider_factory(api_key, model), cache_dir=str(root / "data" / "llm" / "cache"))
    return ask(question, store, get_chat_strategy(pair.chat), runner), runner


def format_answer(result: Answer) -> str:
    by_id = {p.id: p for p in result.retrieved}
    lines = [result.text]
    if result.citations:
        lines += ["", "**Sources**"]
        for i, pid in enumerate(result.citations, 1):
            p = by_id[pid]
            lines.append(f"{i}. [{p.title or p.video_id} at {hms(p.start)}]({p.link})")
    return "\n".join(lines)


def search_details(result: Answer) -> str:
    """What was searched and found, for the step under the answer."""
    lines = ["Searched with: " + " | ".join(result.queries), "", f"{len(result.retrieved)} passages found:"]
    lines += [f"- {p.id} at {hms(p.start)}: {p.text[:140]}" for p in result.retrieved]
    return "\n".join(lines)


def waiting_text(runner: ToolRunner) -> str:
    reasons = "; ".join(runner.waiting) or "the model did not answer"
    return (f"No answer yet: {reasons}. If the daily quota of this model is used up, pick another model in this "
            f"chat's settings (each model has its own free quota) or try again tomorrow.")
