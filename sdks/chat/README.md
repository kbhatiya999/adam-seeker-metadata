# seeker-sdk-chat

Chat strategies find passages and have a model answer from them, citing passage ids.

| Strategy | Retrieval |
|---|---|
| `keyword@v1` | BM25 with the question as typed |
| `multilingual@v1` | a model (`expand_query@v1`) rewrites the question as keywords in English, Roman Urdu, Devanagari and Bengali; the searches are fused |

Both answer with `answer@v1`: only from the passages, attributed, with citations, or `not_found`.

```python
from seeker_sdk_chat import ask, get_chat_strategy
from seeker_sdk_knowledge import KnowledgeStore
from seeker_sdk_llm import ToolRunner, make_provider

store = KnowledgeStore("data/knowledge", "english-notes", "v1")
result = ask("Which verse says the earth is spread out?", store, get_chat_strategy("multilingual"),
             ToolRunner(make_provider("queue")))
```
