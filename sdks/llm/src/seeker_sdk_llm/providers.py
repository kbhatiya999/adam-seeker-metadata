"""Providers run tool requests (entry-point group `seeker.llm_providers`).

`queue` hands requests over as files, so anything that can read and write files can be the model: a person, a
subagent, a script that calls an API. Gemini will be another provider; nothing else has to change.
"""

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .tools import Pending, ToolRequest

DEFAULT_QUEUE_DIR = "data/llm/queue"

HOW_TO_ANSWER = (
    "Follow `instructions` using `input`. Write ONLY a JSON file to `answer_to` containing "
    '{"id": "<this id>", "output": <your answer>, "worker": "<who answered>"}, where <your answer> matches '
    "`output_schema`. Do not edit or delete this file; the next run checks the answer, caches it and removes both."
)


class Provider:
    name = ""

    @property
    def key(self) -> str:
        """Who answered, for the cache folder and reports: `queue`, `gemini/<model>` ... Answers from different
        providers or models are kept apart, so comparing them never mixes their answers."""
        return self.name

    def run(self, request: ToolRequest) -> Union[Dict[str, Any], Pending]:
        """The raw output (to be checked against the schema) or Pending."""
        raise NotImplementedError

    def accept(self, request: ToolRequest) -> None:
        """The output was valid and has been cached."""

    def reject(self, request: ToolRequest, errors: List[str]) -> None:
        """The output did not match the schema."""


class FakeProvider(Provider):
    """For tests: `responder(request)` returns the output (or Pending)."""
    name = "fake"

    def __init__(self, responder: Callable[[ToolRequest], Union[Dict[str, Any], Pending]]):
        self.responder = responder
        self.calls: List[ToolRequest] = []

    def run(self, request):
        self.calls.append(request)
        return self.responder(request)


class QueueProvider(Provider):
    """File hand-off: `<root>/pending/<id>.json` is the request, a worker writes `<root>/done/<id>.json`.
    A rejected answer moves to `<root>/rejected/` with the reasons, and the request stays pending."""
    name = "queue"

    def __init__(self, root: str = DEFAULT_QUEUE_DIR):
        self.root = Path(root)

    def _path(self, state: str, request_id: str) -> Path:
        return self.root / state / f"{request_id}.json"

    def run(self, request):
        done = self._path("done", request.id)
        if done.exists():
            try:
                data = json.loads(done.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                self.reject(request, [f"not valid JSON: {e}"])
                return Pending(request.id, "answer was not valid JSON")
            return data.get("output", data) if isinstance(data, dict) else data
        pending = self._path("pending", request.id)
        if not pending.exists():
            pending.parent.mkdir(parents=True, exist_ok=True)
            body = {**request.to_dict(), "answer_to": str(done), "how_to_answer": HOW_TO_ANSWER}
            pending.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        return Pending(request.id, f"waiting for {done}")

    def accept(self, request):
        for state in ("pending", "done"):
            path = self._path(state, request.id)
            if path.exists():
                path.unlink()

    def reject(self, request, errors):
        done, rejected = self._path("done", request.id), self._path("rejected", request.id)
        rejected.parent.mkdir(parents=True, exist_ok=True)
        answer = done.read_text(encoding="utf-8") if done.exists() else ""
        rejected.write_text(json.dumps({"id": request.id, "errors": errors, "answer": answer}, ensure_ascii=False,
                                       indent=2), encoding="utf-8")
        if done.exists():
            done.unlink()

    def status(self) -> Dict[str, int]:
        return {state: len(list((self.root / state).glob("*.json"))) if (self.root / state).exists() else 0
                for state in ("pending", "done", "rejected")}

    def pending_files(self, tool: Optional[str] = None) -> List[str]:
        folder = self.root / "pending"
        files = sorted(folder.glob("*.json")) if folder.exists() else []
        return [str(f) for f in files if tool is None or f.name.startswith(tool + "-")]


def make_provider(name: str, **options) -> Provider:
    """A provider by plugin name; `queue` takes `root`."""
    from seeker_sdk_core import plugins
    cls = plugins.load(plugins.LLM_PROVIDERS, name)
    return cls(**{k: v for k, v in options.items() if v is not None})


def provider_names() -> List[str]:
    from seeker_sdk_core import plugins
    return plugins.names(plugins.LLM_PROVIDERS)


def default_provider_name() -> str:
    return (os.environ.get("SEEKER_LLM_PROVIDER") or "queue").strip()
