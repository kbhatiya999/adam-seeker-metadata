import json

from seeker_sdk_llm import (FakeProvider, Pending, QueueProvider, Tool, ToolRunner, make_provider, provider_names,
                            validate)

TOOL = Tool("summary", "v1", "Summarise the text in one sentence.", {
    "type": "object", "required": ["summary"],
    "properties": {"summary": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}},
})


def test_schema_subset():
    assert validate({"summary": "x", "tags": ["a"]}, TOOL.output_schema) == []
    assert validate({"tags": [1]}, TOOL.output_schema) == ["$: missing 'summary'", "$.tags[0]: expected string, got int"]
    assert validate("x", {"type": "string", "enum": ["a", "b"]}) == ["$: 'x' is not one of ['a', 'b']"]
    assert validate(True, {"type": "integer"}) and validate([], {"type": "array", "minItems": 1})


def test_request_ids_are_stable_and_change_with_the_instructions_or_input():
    a, b = TOOL.request({"text": "hi"}), TOOL.request({"text": "hi"})
    assert a.id == b.id and a.id.startswith("summary-")
    assert TOOL.request({"text": "other"}).id != a.id
    assert Tool("summary", "v1", "Different words.", TOOL.output_schema).request({"text": "hi"}).id != a.id


def test_runner_caches_answers_and_checks_them(tmp_path):
    provider = FakeProvider(lambda r: {"summary": "short " + r.input["text"]})
    runner = ToolRunner(provider, cache_dir=str(tmp_path / "cache"))
    assert runner.call(TOOL, {"text": "a"}) == {"summary": "short a"}
    assert ToolRunner(provider, cache_dir=str(tmp_path / "cache")).call(TOOL, {"text": "a"}) == {"summary": "short a"}
    assert len(provider.calls) == 1  # the second runner was served from the cache
    bad = ToolRunner(FakeProvider(lambda r: {"wrong": 1}), cache_dir=str(tmp_path / "c2"))
    result = bad.call(TOOL, {"text": "b"})
    assert isinstance(result, Pending) and "missing 'summary'" in result.reason


def test_budget_caps_requests_per_run(tmp_path):
    runner = ToolRunner(FakeProvider(lambda r: {"summary": "s"}), cache_dir=str(tmp_path), max_requests=2)
    results = [runner.call(TOOL, {"text": str(i)}) for i in range(3)]
    assert results[:2] == [{"summary": "s"}] * 2 and isinstance(results[2], Pending) and "budget" in results[2].reason
    assert runner.waiting == {"budget for this run is used up": 1}


def test_queue_round_trip_reject_and_accept(tmp_path):
    queue = QueueProvider(str(tmp_path / "q"))
    runner = ToolRunner(queue, cache_dir=str(tmp_path / "cache"))
    first = runner.call(TOOL, {"text": "hello"})
    assert isinstance(first, Pending)
    [pending] = queue.pending_files()
    body = json.loads(open(pending, encoding="utf-8").read())
    assert body["instructions"] == TOOL.instructions and body["input"] == {"text": "hello"}
    assert body["answer_to"].endswith(f"done/{body['id']}.json") and "output_schema" in body
    assert queue.status() == {"pending": 1, "done": 0, "rejected": 0}

    done = tmp_path / "q" / "done" / f"{body['id']}.json"
    done.parent.mkdir(parents=True)
    done.write_text(json.dumps({"id": body["id"], "output": {"nope": 1}}))   # wrong shape
    assert isinstance(runner.call(TOOL, {"text": "hello"}), Pending)
    assert queue.status() == {"pending": 1, "done": 0, "rejected": 1}

    done.write_text("{not json")                                               # broken file
    assert isinstance(runner.call(TOOL, {"text": "hello"}), Pending)

    done.write_text(json.dumps({"id": body["id"], "output": {"summary": "hi"}, "worker": "test"}))
    assert runner.call(TOOL, {"text": "hello"}) == {"summary": "hi"}
    assert queue.status()["pending"] == 0 and queue.status()["done"] == 0
    assert runner.call(TOOL, {"text": "hello"}) == {"summary": "hi"}           # cached now
    cached = list((tmp_path / "cache" / "queue" / "summary@v1").glob("*.json"))
    assert len(cached) == 1 and json.loads(cached[0].read_text())["provider"] == "queue"


def test_answers_are_cached_per_provider_so_models_never_mix(tmp_path):
    a = FakeProvider(lambda r: {"summary": "from a"})
    b = type("Other", (FakeProvider,), {"name": "other"})(lambda r: {"summary": "from b"})
    assert ToolRunner(a, str(tmp_path)).call(TOOL, {"text": "x"}) == {"summary": "from a"}
    assert ToolRunner(b, str(tmp_path)).call(TOOL, {"text": "x"}) == {"summary": "from b"}   # not a's cached answer
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fake", "other"]


def test_queue_is_a_plugin(tmp_path):
    assert "queue" in provider_names()
    assert isinstance(make_provider("queue", root=str(tmp_path)), QueueProvider)
