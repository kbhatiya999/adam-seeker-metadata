"""Run the questions against one (processing strategy, chat strategy) pair, score, save and compare runs."""

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from seeker_sdk_chat import ChatStrategy, Retriever
from seeker_sdk_knowledge import KnowledgeStore
from seeker_sdk_llm import Pending, Tool, ToolRunner, Waiting, read_prompt

from .questions import Question
from .scoring import keyword_score, retrieval_hit

DEFAULT_EVAL_DIR = "data/eval"
JUDGE_TOOL = Tool("judge", "v1", read_prompt("seeker_sdk_eval", "judge_v1.md"), {
    "type": "object", "required": ["verdict", "reason"],
    "properties": {"verdict": {"type": "string", "enum": ["correct", "partial", "wrong", "declined"]},
                   "reason": {"type": "string"}},
})


@dataclass
class Row:
    id: str
    type: str
    lang: str
    status: str = "waiting"              # done | waiting
    retrieval: Optional[float] = None    # share of expected places among the retrieved passages
    keyword: Optional[float] = None      # share of must_mention items in the answer
    verdict: Optional[str] = None        # correct | partial | wrong | declined (answered: unanswerable not declined)
    reason: str = ""
    answer: str = ""
    citations: List[str] = field(default_factory=list)
    retrieved: List[str] = field(default_factory=list)
    queries: List[str] = field(default_factory=list)


@dataclass
class EvalRun:
    processing: str
    chat: str
    videos: List[str]
    started: str
    rows: List[Row]
    summary: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)

    @property
    def pair(self) -> str:
        return f"{self.processing}__{self.chat}"


def evaluate(questions: Iterable[Question], store: KnowledgeStore, strategy: ChatStrategy, runner: ToolRunner,
             videos: Optional[Iterable[str]] = None, judge: bool = True, judge_tool: Tool = JUDGE_TOOL) -> EvalRun:
    videos = sorted(videos) if videos else []
    index = Retriever(store.passages(videos or None))
    rows: List[Row] = []
    for q in questions:
        row = Row(q.id, q.type, q.lang)
        rows.append(row)
        result = strategy.answer(q.question, index, runner)
        if isinstance(result, Waiting):
            continue
        row.answer, row.citations, row.queries = result.text, result.citations, result.queries
        row.retrieved = [f"{p.id}@{p.when}" for p in result.retrieved]
        if q.unanswerable:
            row.verdict, row.status = ("declined" if result.not_found else "answered"), "done"
            continue
        row.retrieval = retrieval_hit(result.retrieved, q.places)
        row.keyword = keyword_score(result.text, q.must_mention)
        if result.not_found:
            row.verdict, row.status = "declined", "done"
        elif not judge:
            row.status = "done"
        else:
            verdict = runner.call(judge_tool, {"question": q.question, "reference": q.answer, "answer": result.text})
            if not isinstance(verdict, Pending):
                row.verdict, row.reason, row.status = verdict["verdict"], verdict["reason"], "done"
    run = EvalRun(f"{store.strategy}@{store.version}", f"{strategy.name}@{strategy.version}", videos,
                  datetime.now().isoformat(timespec="seconds"), rows,
                  settings={"chat": strategy.settings(), "processing": store.manifest().get("settings", {}),
                            "judge": judge_tool.key if judge else None})
    run.summary = summarize(rows, runner)
    return run


def _mean(values: List[float]) -> Optional[float]:
    return round(sum(values) / len(values), 3) if values else None


def _score(rows: List[Row]) -> Optional[float]:
    judged = [r for r in rows if r.verdict in ("correct", "partial", "wrong", "declined")]
    return _mean([1.0 if r.verdict == "correct" else 0.5 if r.verdict == "partial" else 0.0 for r in judged])


def summarize(rows: List[Row], runner: Optional[ToolRunner] = None) -> Dict[str, Any]:
    done = [r for r in rows if r.status == "done"]
    answerable = [r for r in done if r.type != "unanswerable"]
    unanswerable = [r for r in done if r.type == "unanswerable"]
    summary: Dict[str, Any] = {
        "questions": len(rows), "done": len(done), "waiting": len(rows) - len(done),
        "score": _score(answerable),
        "retrieval": _mean([r.retrieval for r in answerable if r.retrieval is not None]),
        "keywords": _mean([r.keyword for r in answerable if r.keyword is not None]),
        "verdicts": dict(Counter(r.verdict for r in answerable if r.verdict)),
        "declined_wrongly": sum(r.verdict == "declined" for r in answerable),
        "not_found_ok": _mean([1.0 if r.verdict == "declined" else 0.0 for r in unanswerable]),
        "by_lang": {lang: {"n": len(rs), "score": _score(rs),
                           "retrieval": _mean([r.retrieval for r in rs if r.retrieval is not None])}
                    for lang in sorted({r.lang for r in answerable})
                    for rs in [[r for r in answerable if r.lang == lang]]},
    }
    if runner is not None:
        summary["model_requests"] = {"sent": runner.sent, "from_cache": runner.cached, "answered": runner.answered}
    return summary


def save(run: EvalRun, root: str = DEFAULT_EVAL_DIR) -> Path:
    """runs/<pair>__<time>.json (history) and latest/<pair>.json (what compare reads)."""
    data = json.dumps(asdict(run), ensure_ascii=False, indent=2)
    stamp = run.started.replace(":", "").replace("-", "")
    history = Path(root) / "runs" / f"{run.pair}__{stamp}.json"
    latest = Path(root) / "latest" / f"{run.pair}.json"
    for path in (history, latest):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
    return latest


def latest_runs(root: str = DEFAULT_EVAL_DIR) -> List[Dict[str, Any]]:
    folder = Path(root) / "latest"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))] if folder.exists() else []


def _pct(value: Optional[float]) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


def comparison_table(runs: List[Dict[str, Any]]) -> str:
    """Markdown table, best score first."""
    head = ("| processing | chat | questions | score | retrieval | keywords | correct/partial/wrong/declined "
            "| not found ok | en | roman-ur |")
    lines = [head, "|" + "---|" * 10]
    for r in sorted(runs, key=lambda r: -(r["summary"].get("score") or 0)):
        s, v = r["summary"], r["summary"].get("verdicts", {})
        lang = s.get("by_lang", {})
        counts = "/".join(str(v.get(k, 0)) for k in ("correct", "partial", "wrong", "declined"))
        waiting = f" ({s['waiting']} waiting)" if s.get("waiting") else ""
        lines.append(f"| {r['processing']} | {r['chat']} | {s['done']}{waiting} | {_pct(s.get('score'))} "
                     f"| {_pct(s.get('retrieval'))} | {_pct(s.get('keywords'))} | {counts} "
                     f"| {_pct(s.get('not_found_ok'))} | {_pct(lang.get('en', {}).get('score'))} "
                     f"| {_pct(lang.get('roman-ur', {}).get('score'))} |")
    return "\n".join(lines)
