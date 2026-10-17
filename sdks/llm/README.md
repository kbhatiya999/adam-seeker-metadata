# seeker-sdk-llm

Language-model **tools** and the **providers** that run them, with a cache and a per-run budget.

```python
from seeker_sdk_llm import Tool, ToolRunner, Pending, make_provider

tool = Tool("summary", "v1", "Summarise the text in one sentence.",
            {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}})
runner = ToolRunner(make_provider("queue"))          # cache in data/llm/cache, queue in data/llm/queue
result = runner.call(tool, {"text": "..."})
if isinstance(result, Pending):
    print("answer data/llm/queue/pending/*.json, then run again")
```

- `queue` provider: writes the request as a file; any worker (a person, a subagent, a script) answers it.
- The cache key is a hash of tool, instructions and input; an answer is never requested twice.
- Answers are checked against `output_schema` (a small JSON Schema subset, no dependency).
- Gemini will be another provider in the `seeker.llm_providers` entry-point group.
