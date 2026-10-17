# seeker-sdk-eval

Runs `eval/questions` (format in `eval/README.md`) against a (processing strategy, chat strategy) pair and scores
it: retrieval (the right video and time among the retrieved passages), `must_mention` keywords, a model judge
(`judge@v1`) and "not found" on unanswerable questions. Runs are saved to `data/eval/runs/` and
`data/eval/latest/`; `comparison_table` puts the latest run of every pair side by side.

```python
from seeker_sdk_chat import get_chat_strategy
from seeker_sdk_eval import evaluate, load, save, select
from seeker_sdk_knowledge import KnowledgeStore
from seeker_sdk_llm import ToolRunner, make_provider

videos = ["OCZ0vysB4xY"]
run = evaluate(select(load("eval/questions"), videos), KnowledgeStore("data/knowledge", "english-notes", "v1"),
               get_chat_strategy("keyword"), ToolRunner(make_provider("queue")), videos)
save(run)
```
