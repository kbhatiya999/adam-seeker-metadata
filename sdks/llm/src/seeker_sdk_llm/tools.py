"""Tools: a task for a language model, written once and run by any provider.

A Tool is instructions plus a JSON input that must come back as JSON matching `output_schema`. Nothing in a Tool
says WHO runs it: a queue worked by people or subagents, Gemini, or a fake in tests. Changing the instructions
changes every request id, so an edited prompt never reuses old answers; give it a new version anyway, so both can
be compared.
"""

import hashlib
import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Dict


@dataclass(frozen=True)
class Tool:
    name: str
    version: str
    instructions: str
    output_schema: Dict[str, Any] = field(hash=False, compare=False, default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"

    def request(self, input: Dict[str, Any]) -> "ToolRequest":
        canonical = json.dumps({"tool": self.key, "instructions": self.instructions, "input": input},
                               sort_keys=True, ensure_ascii=False)
        return ToolRequest(f"{self.name}-{hashlib.sha256(canonical.encode()).hexdigest()[:20]}", self, input)


@dataclass(frozen=True)
class ToolRequest:
    id: str
    tool: Tool
    input: Dict[str, Any] = field(hash=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "tool": self.tool.name, "version": self.tool.version,
                "instructions": self.tool.instructions, "input": self.input, "output_schema": self.tool.output_schema}


@dataclass(frozen=True)
class Pending:
    """The answer to one request is not there yet (a worker has to answer it, or the daily budget is used up)."""
    request_id: str
    reason: str = ""


@dataclass(frozen=True)
class Waiting:
    """A larger job (a video, a question) is waiting for `requests` tool answers; run it again later."""
    requests: int = 1


def read_prompt(package: str, filename: str) -> str:
    """Instructions kept as a file next to the code (`<package>/prompts/<filename>`), so a tweak is a readable diff."""
    return resources.files(package).joinpath("prompts", filename).read_text(encoding="utf-8")
