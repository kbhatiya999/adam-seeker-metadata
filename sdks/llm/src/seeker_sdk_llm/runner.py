"""Runs tools through a provider, with a cache and a per-run budget.

A request answered once is stored in `<cache>/<provider key>/<tool>@<version>/<id>.json` and never sent again, so re-running a
pipeline (tomorrow, after a crash, with one more video) only asks for what is new. `max_requests` caps how many
requests one run hands to the provider (a daily quota, for example); the rest wait until the next run.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .providers import Provider
from .schema import validate
from .tools import Pending, Tool, ToolRequest

DEFAULT_CACHE_DIR = "data/llm/cache"


class ToolRunner:
    def __init__(self, provider: Provider, cache_dir: str = DEFAULT_CACHE_DIR, max_requests: Optional[int] = None):
        self.provider = provider
        self.cache_dir = Path(cache_dir)
        self.max_requests = max_requests
        self.sent = 0      # requests handed to the provider in this run
        self.cached = 0    # answers served from the cache
        self.answered = 0  # new answers accepted in this run
        self.waiting: Counter = Counter()  # why requests are still waiting (quota, budget, rejected answer ...)

    def _wait(self, pending: Pending) -> Pending:
        reason = pending.reason if not pending.reason.startswith("waiting for ") else "waiting for a worker to answer"
        self.waiting[reason] += 1
        return pending

    def _cache_path(self, request: ToolRequest) -> Path:
        return self.cache_dir / self.provider.key / request.tool.key / f"{request.id}.json"

    def call(self, tool: Tool, input: Dict[str, Any]) -> Union[Dict[str, Any], Pending]:
        return self.run(tool.request(input))

    def run(self, request: ToolRequest) -> Union[Dict[str, Any], Pending]:
        cached = self._cache_path(request)
        if cached.exists():
            self.cached += 1
            return json.loads(cached.read_text(encoding="utf-8"))["output"]
        if self.max_requests is not None and self.sent >= self.max_requests:
            return self._wait(Pending(request.id, "budget for this run is used up"))
        self.sent += 1
        result = self.provider.run(request)
        if isinstance(result, Pending):
            return self._wait(result)
        errors = validate(result, request.tool.output_schema)
        if errors:
            self.provider.reject(request, errors)
            return self._wait(Pending(request.id, "answer rejected: " + "; ".join(errors[:3])))
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"id": request.id, "tool": request.tool.key, "provider": self.provider.key,
                                      "input": request.input, "output": result}, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        self.provider.accept(request)
        self.answered += 1
        return result
