"""Chat strategies (entry-point group `seeker.chat_strategies`): question + passages -> attributed answer.

A strategy decides how to find passages and how to ask the model. Both steps are tools run by a ToolRunner, so a
strategy works with any provider and returns Waiting while answers are outstanding.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Union

from seeker_sdk_knowledge import Passage
from seeker_sdk_llm import Pending, Tool, ToolRunner, Waiting, read_prompt

from .retrieval import Retriever

ANSWER_TOOL = Tool("answer", "v1", read_prompt("seeker_sdk_chat", "answer_v1.md"), {
    "type": "object", "required": ["answer", "citations", "not_found"],
    "properties": {"answer": {"type": "string"}, "citations": {"type": "array", "items": {"type": "string"}},
                   "not_found": {"type": "boolean"}},
})
EXPAND_TOOL = Tool("expand_query", "v1", read_prompt("seeker_sdk_chat", "expand_query_v1.md"), {
    "type": "object", "required": ["queries"],
    "properties": {"queries": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
})


@dataclass
class Answer:
    text: str
    citations: List[str]
    not_found: bool
    retrieved: List[Passage]
    queries: List[str] = field(default_factory=list)


@dataclass
class Retrieved:
    passages: List[Passage]
    queries: List[str]


def passage_view(p: Passage) -> Dict[str, Any]:
    return {"id": p.id, "title": p.title, "at": p.when, "text": p.text}


class ChatStrategy:
    name = ""
    version = "v1"
    description = ""

    def __init__(self, k: int = 6, answer_tool: Tool = ANSWER_TOOL):
        self.k, self.answer_tool = k, answer_tool

    def settings(self) -> Dict[str, Any]:
        return {"k": self.k, "answer_tool": self.answer_tool.key}

    def retrieve(self, question: str, index: Retriever, runner: ToolRunner) -> Union[Retrieved, Waiting]:
        raise NotImplementedError

    def answer(self, question: str, index: Retriever, runner: ToolRunner) -> Union[Answer, Waiting]:
        found = self.retrieve(question, index, runner)
        if isinstance(found, Waiting):
            return found
        output = runner.call(self.answer_tool, {"question": question,
                                                "passages": [passage_view(p) for p in found.passages]})
        if isinstance(output, Pending):
            return Waiting(1)
        known = {p.id for p in found.passages}
        cited = [c for c in output["citations"] if c in known]  # a model must not cite what it was not given
        return Answer(output["answer"], cited, bool(output["not_found"]), found.passages, found.queries)


class KeywordStrategy(ChatStrategy):
    """BM25 with the question as typed, then the answer tool."""
    name = "keyword"
    version = "v1"
    description = "keyword search with the question as typed, then a model answers from the top passages"

    def retrieve(self, question, index, runner):
        return Retrieved(index.search(question, self.k), [question])


class MultilingualStrategy(ChatStrategy):
    """A model first rewrites the question as keywords in English, Roman Urdu, Devanagari and Bengali; all are
    searched and fused. Meant for stores whose text is in the caption scripts."""
    name = "multilingual"
    version = "v1"
    description = "a model rewrites the question into keywords in several scripts, fused keyword search, then answer"

    def __init__(self, k: int = 6, answer_tool: Tool = ANSWER_TOOL, expand_tool: Tool = EXPAND_TOOL):
        super().__init__(k, answer_tool)
        self.expand_tool = expand_tool

    def settings(self):
        return {**super().settings(), "expand_tool": self.expand_tool.key}

    def retrieve(self, question, index, runner):
        output = runner.call(self.expand_tool, {"question": question})
        if isinstance(output, Pending):
            return Waiting(1)
        queries = [question] + list(output["queries"])
        return Retrieved(index.search_many(queries, self.k), queries)
