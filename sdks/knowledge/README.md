# seeker-sdk-knowledge

Processing strategies turn transcripts into **passages** that chat strategies search. Each strategy and version has
its own folder of text files: `data/knowledge/<strategy>@<version>/` (passages JSONL per video, notes, manifest).

| Strategy | Model | Passages |
|---|---|---|
| `chunks@v1` | no | raw caption text in 3-minute windows |
| `english-notes@v1` | yes (`english_notes@v1`) | attributed English notes with times, references and topics |

```python
from seeker_sdk_core import MasterList
from seeker_sdk_knowledge import KnowledgeStore, get_strategy, process
from seeker_sdk_llm import ToolRunner, make_provider

strategy = get_strategy("english-notes")
store = KnowledgeStore("data/knowledge", strategy.name, strategy.version)
report = process(strategy, MasterList.load_strict("data/videos_master.json"), store,
                 ToolRunner(make_provider("queue")), videos=["OCZ0vysB4xY"])
print(report.done, report.waiting)   # waiting: answers still outstanding; run again later
```
