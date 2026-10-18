"""`seeker llm | knowledge | ask | eval`: language-model tools, processing strategies, chat strategies, evaluation.

Every command that needs a model runs its tools through a provider (`--provider`, or SEEKER_LLM_PROVIDER; default
`queue`). With `queue`, requests are written to data/llm/queue/pending/ and a worker answers them; the command then
exits with code 75 ("try again later") and running it again continues where it stopped.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from seeker_sdk_chat import Answer, ask, chat_strategy_names, get_chat_strategy
from seeker_sdk_core import DEFAULT_MASTER_FILE, MasterList, SeekerError
from seeker_sdk_eval import (DEFAULT_EVAL_DIR, DEFAULT_QUESTIONS_DIR, comparison_table, evaluate, latest_runs, load,
                             save, select)
from seeker_sdk_knowledge import (DEFAULT_KNOWLEDGE_DIR, DEFAULT_TRANSCRIPTS_DIR, KnowledgeStore, get_strategy, hms,
                                  process, strategy_names)
from seeker_sdk_llm import (DEFAULT_CACHE_DIR, DEFAULT_QUEUE_DIR, QueueProvider, ToolRunner, Waiting,
                            default_provider_name, make_provider, provider_names)

WAITING = 75  # EX_TEMPFAIL: answers from the model are outstanding; run the same command again later


def _videos(value: Optional[str]) -> Optional[List[str]]:
    return [v.strip() for v in value.split(",") if v.strip()] if value else None


def _runner(args) -> ToolRunner:
    return ToolRunner(make_provider(args.provider), DEFAULT_CACHE_DIR, args.max_requests)


def _model_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--provider", default=default_provider_name(),
                   help=f"who runs the model tools: {', '.join(provider_names()) or 'queue'} (default: queue, or "
                        "SEEKER_LLM_PROVIDER)")
    p.add_argument("--max-requests", type=int, help="at most this many new model requests in this run (a daily quota)")


def _requests_line(runner: ToolRunner) -> str:
    line = f"Model requests this run: {runner.sent} sent, {runner.cached} from cache, {runner.answered} answered"
    if runner.waiting:
        line += "\nWaiting because: " + "; ".join(f"{reason} ({n})" for reason, n in runner.waiting.most_common())
    return line


def _store(name: str) -> KnowledgeStore:
    strategy = get_strategy(name)
    return KnowledgeStore(DEFAULT_KNOWLEDGE_DIR, strategy.name, strategy.version)


def _waiting_hint(provider: str) -> str:
    if provider == "queue":
        return (f"Answer the requests in {DEFAULT_QUEUE_DIR}/pending/ (see `how_to_answer` in each file), "
                "then run the same command again.")
    return "Run the same command again later."


# ---------------------------------------------------------------- seeker llm
def _llm_status(args) -> int:
    print("queue:", ", ".join(f"{k} {v}" for k, v in QueueProvider(DEFAULT_QUEUE_DIR).status().items()))
    cache = Path(DEFAULT_CACHE_DIR)
    counts: dict = {}
    for f in (cache.rglob("*.json") if cache.exists() else []):   # <provider key>/<tool>@<version>/<id>.json
        key = str(f.parent.relative_to(cache))
        counts[key] = counts.get(key, 0) + 1
    print("cache:", ", ".join(f"{k} {n}" for k, n in sorted(counts.items())) or "empty")
    return 0


def _llm_pending(args) -> int:
    files = QueueProvider(DEFAULT_QUEUE_DIR).pending_files(args.tool)
    for path in files[:args.limit] if args.limit else files:
        print(path)
    return 0


# ---------------------------------------------------------------- seeker knowledge
def _knowledge_strategies(args) -> int:
    for name in strategy_names():
        s = get_strategy(name)
        print(f"{s.name + '@' + s.version:<20} {'model' if s.uses_llm else 'no model':<9} {s.description}")
    return 0


def _knowledge_process(args) -> int:
    strategy = get_strategy(args.strategy)
    store = KnowledgeStore(DEFAULT_KNOWLEDGE_DIR, strategy.name, strategy.version)
    try:
        master = MasterList.load_strict(args.master_file)
    except SeekerError as e:
        sys.exit(str(e))
    runner = _runner(args) if strategy.uses_llm else None
    report = process(strategy, master, store, runner, _videos(args.videos), DEFAULT_TRANSCRIPTS_DIR, args.force)
    print(f"{strategy.name}@{strategy.version} -> {store.dir}")
    if report.done:
        print("  done:", ", ".join(report.done))
    if report.skipped:
        print("  already done (use --force to redo):", ", ".join(report.skipped))
    if report.no_transcript:
        print("  no transcript yet:", ", ".join(report.no_transcript))
    if report.waiting:
        print("  waiting for the model:", ", ".join(f"{v} ({n} answers)" for v, n in report.waiting.items()))
    if runner:
        print(_requests_line(runner))
    if report.waiting:
        print(_waiting_hint(args.provider))
        return WAITING
    return 0


def _knowledge_status(args) -> int:
    root = Path(DEFAULT_KNOWLEDGE_DIR)
    folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []
    if not folders:
        print(f"Nothing processed yet ({root} is empty).")
    for folder in folders:
        strategy, _, version = folder.name.partition("@")
        store = KnowledgeStore(DEFAULT_KNOWLEDGE_DIR, strategy, version)
        videos = store.manifest().get("videos", {})
        print(f"{folder.name}: {len(videos)} videos, {sum(v['passages'] for v in videos.values())} passages")
    return 0


# ---------------------------------------------------------------- seeker ask
def _print_answer(result: Answer) -> None:
    print(result.text)
    by_id = {p.id: p for p in result.retrieved}
    if result.citations:
        print("\nSources:")
        for i, pid in enumerate(result.citations, 1):
            p = by_id[pid]
            print(f"  [{i}] {p.title} at {hms(p.start)}  {p.link}  ({pid})")


def _ask(args) -> int:
    runner = _runner(args)
    result = ask(args.question, _store(args.processing), get_chat_strategy(args.chat, k=args.k), runner,
                 _videos(args.videos))
    if isinstance(result, Waiting):
        print(f"Waiting for the model ({result.requests} answer). {_waiting_hint(args.provider)}")
        return WAITING
    _print_answer(result)
    return 0


# ---------------------------------------------------------------- seeker eval
def _eval_questions(args) -> int:
    qs = select(load(DEFAULT_QUESTIONS_DIR), _videos(args.videos))
    for q in qs:
        print(f"{q.id:<18} {q.type:<12} {q.lang:<8} {q.question[:80]}")
    print(f"{len(qs)} questions")
    return 0


def _pct(v: Optional[float]) -> str:
    return "-" if v is None else f"{v * 100:.0f}%"


def _eval_run(args) -> int:
    videos = _videos(args.videos)
    questions = select(load(DEFAULT_QUESTIONS_DIR), videos)
    if not questions:
        sys.exit("No questions for these videos (see eval/questions).")
    store = _store(args.processing)
    missing = [v for v in (videos or []) if not store.has(v)]
    if missing:
        sys.exit(f"{store.dir.name} has not processed {', '.join(missing)} yet: "
                 f"seeker knowledge process --strategy {args.processing} --videos {','.join(missing)}")
    runner = _runner(args)
    run = evaluate(questions, store, get_chat_strategy(args.chat, k=args.k), runner, videos, judge=not args.no_judge)
    path = save(run, DEFAULT_EVAL_DIR)
    s = run.summary
    print(f"{run.processing} + {run.chat} on {len(questions)} questions"
          + (f" (videos: {', '.join(videos)})" if videos else ""))
    for r in run.rows:
        print(f"  {r.id:<18} {r.lang:<8} {r.status:<7} retrieval {_pct(r.retrieval):>4}  keywords {_pct(r.keyword):>4}"
              f"  {r.verdict or '-'}")
    print(f"Score {_pct(s['score'])}, retrieval {_pct(s['retrieval'])}, keywords {_pct(s['keywords'])}, "
          f"not found ok {_pct(s['not_found_ok'])}, verdicts {s['verdicts']}")
    print(_requests_line(runner))
    print(f"Saved {path}")
    if s["waiting"]:
        print(f"{s['waiting']} questions are waiting for the model. {_waiting_hint(args.provider)}")
        return WAITING
    return 0


def _eval_compare(args) -> int:
    runs = latest_runs(DEFAULT_EVAL_DIR)
    print(comparison_table(runs) if runs else "No evaluation runs yet (seeker eval run ...).")
    return 0


# ---------------------------------------------------------------- parsers
def add_parsers(sub) -> None:
    llm = sub.add_parser("llm", help="the model tool queue and cache")
    lsub = llm.add_subparsers(dest="llm_cmd", required=True)
    lsub.add_parser("status", help="requests pending/done/rejected and cached answers per tool").set_defaults(func=_llm_status)
    lp = lsub.add_parser("pending", help="list pending request files (for a worker to answer)")
    lp.add_argument("--tool", help="only this tool (english_notes, expand_query, answer, judge)")
    lp.add_argument("--limit", type=int)
    lp.set_defaults(func=_llm_pending)

    kn = sub.add_parser("knowledge", help="processing strategies: transcripts -> searchable passages")
    ksub = kn.add_subparsers(dest="knowledge_cmd", required=True)
    ksub.add_parser("strategies", help="list the processing strategies").set_defaults(func=_knowledge_strategies)
    kp = ksub.add_parser("process", help="run a processing strategy over videos with transcripts")
    kp.add_argument("--strategy", required=True, help=f"one of: {', '.join(strategy_names())}")
    kp.add_argument("--videos", help="comma separated video ids (default: every video with a transcript)")
    kp.add_argument("--force", action="store_true", help="redo videos that are already processed")
    kp.add_argument("--master-file", default=DEFAULT_MASTER_FILE)
    _model_options(kp)
    kp.set_defaults(func=_knowledge_process)
    ksub.add_parser("status", help="what each strategy has processed").set_defaults(func=_knowledge_status)

    ak = sub.add_parser("ask", help="ask a question with a chat strategy over processed videos")
    ak.add_argument("question")
    ak.add_argument("--processing", required=True, help=f"processing strategy: {', '.join(strategy_names())}")
    ak.add_argument("--chat", default="keyword", help=f"chat strategy: {', '.join(chat_strategy_names())}")
    ak.add_argument("--videos", help="comma separated video ids to search (default: all processed)")
    ak.add_argument("--k", type=int, default=6, help="passages given to the model (default 6)")
    _model_options(ak)
    ak.set_defaults(func=_ask)

    ev = sub.add_parser("eval", help="evaluate (processing, chat) strategy pairs on eval/questions")
    esub = ev.add_subparsers(dest="eval_cmd", required=True)
    eq = esub.add_parser("questions", help="list the questions for some videos")
    eq.add_argument("--videos")
    eq.set_defaults(func=_eval_questions)
    er = esub.add_parser("run", help="answer, score and save; run again to continue when waiting")
    er.add_argument("--processing", required=True, help=f"processing strategy: {', '.join(strategy_names())}")
    er.add_argument("--chat", required=True, help=f"chat strategy: {', '.join(chat_strategy_names())}")
    er.add_argument("--videos", help="only questions about these videos (comma separated)")
    er.add_argument("--k", type=int, default=6)
    er.add_argument("--no-judge", action="store_true", help="skip the model judge (keyword and retrieval scores only)")
    _model_options(er)
    er.set_defaults(func=_eval_run)
    esub.add_parser("compare", help="table of the latest run of every pair").set_defaults(func=_eval_compare)
