"""Ask a question with a chat strategy over a knowledge store."""

from typing import Iterable, List, Optional, Union

from seeker_sdk_core import plugins
from seeker_sdk_knowledge import KnowledgeStore
from seeker_sdk_llm import ToolRunner, Waiting

from .retrieval import Retriever
from .strategies import Answer, ChatStrategy


def chat_strategy_names() -> List[str]:
    return plugins.names(plugins.CHAT_STRATEGIES)


def get_chat_strategy(name: str, **settings) -> ChatStrategy:
    return plugins.load(plugins.CHAT_STRATEGIES, name)(**settings)


def ask(question: str, store: KnowledgeStore, strategy: ChatStrategy, runner: ToolRunner,
        videos: Optional[Iterable[str]] = None) -> Union[Answer, Waiting]:
    return strategy.answer(question, Retriever(store.passages(videos)), runner)
