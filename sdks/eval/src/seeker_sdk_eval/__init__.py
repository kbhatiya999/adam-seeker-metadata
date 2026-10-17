"""Seeker SDK eval: run the evaluation questions against (processing strategy, chat strategy) pairs and compare."""

from .questions import DEFAULT_QUESTIONS_DIR, Question, load, select
from .runner import (DEFAULT_EVAL_DIR, JUDGE_TOOL, EvalRun, Row, comparison_table, evaluate, latest_runs, save,
                     summarize)
from .scoring import TOLERANCE, keyword_score, mentions, retrieval_hit

__all__ = ["DEFAULT_EVAL_DIR", "DEFAULT_QUESTIONS_DIR", "JUDGE_TOOL", "TOLERANCE", "EvalRun", "Question", "Row",
           "comparison_table", "evaluate", "keyword_score", "latest_runs", "load", "mentions", "retrieval_hit",
           "save", "select", "summarize"]
__version__ = "0.1.0"
