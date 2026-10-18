"""seeker knowledge / llm / ask / eval end to end, with the file queue and an in-process fake model."""

import json
import os

import pytest

from seeker_cli.main import main
from seeker_sdk_core import plugins
from seeker_sdk_llm import FakeProvider


def model(request):
    if request.tool.name == "english_notes":
        first_line_time = request.input["transcript"].split("]")[0].lstrip("[")   # copy a line's time, as the prompt asks
        return {"notes": [{"start": first_line_time, "kind": "reference", "speaker": "host",
                           "text": "The host cites Sahih Bukhari 5686 about drinking urine.", "refs": ["Sahih Bukhari 5686"]}]}
    if request.tool.name == "answer":
        ids = [p["id"] for p in request.input["passages"]]
        return {"answer": "The host cites Sahih Bukhari 5686.", "citations": ids[:1], "not_found": not ids}
    if request.tool.name == "judge":
        return {"verdict": "correct", "reason": "same number"}
    return {"queries": [request.input["question"]]}


class CliFake(FakeProvider):
    name = "clifake"

    def __init__(self):
        super().__init__(model)


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEEKER_LLM_PROVIDER", raising=False)
    os.makedirs("data/transcripts")
    open("data/transcripts/vidA.srt", "w", encoding="utf-8").write(
        "1\n00:03:00,000 --> 00:03:05,000\nसही बुखारी 5686 मूत्र\n\n2\n00:20:00,000 --> 00:20:05,000\nजमीन\n")
    json.dump({"videos": [{"video_id": "vidA", "title": "Urine"}], "last_updated": "d", "total_videos": 1,
               "channel_url": "u"}, open("m.json", "w"))
    os.makedirs("eval/questions")
    open("eval/questions/vidA.toml", "w", encoding="utf-8").write('''video = "vidA"
[[question]]
id = "vidA-01"
question = "Which Bukhari hadith is about urine?"
lang = "en"
type = "reference"
tags = []
near = "00:03:00"
answer = "Sahih Bukhari 5686."
must_mention = ["5686"]
''')
    plugins.register(plugins.LLM_PROVIDERS, "clifake", CliFake)
    yield
    plugins.unregister(plugins.LLM_PROVIDERS, "clifake")


def run(*argv):
    with pytest.raises(SystemExit) as e:
        main(list(argv))
    return e.value.code


def test_process_with_the_queue_waits_then_continues_after_a_worker_answers(capsys):
    assert run("knowledge", "process", "--strategy", "chunks", "--master-file", "m.json") == 0
    assert "chunks@v1 -> data/knowledge/chunks@v1" in capsys.readouterr().out

    assert run("knowledge", "process", "--strategy", "english-notes", "--master-file", "m.json") == 75
    out = capsys.readouterr().out
    assert "waiting for the model: vidA (2 answers)" in out and "data/llm/queue/pending/" in out
    assert run("llm", "status") == 0 and "pending 2" in capsys.readouterr().out
    assert run("llm", "pending", "--tool", "english_notes") == 0
    pending = capsys.readouterr().out.split()
    for path in pending:                                   # the worker (a subagent, a person ...) answers
        body = json.load(open(path, encoding="utf-8"))
        fake = type("R", (), {"input": body["input"], "tool": type("T", (), {"name": "english_notes"})})
        os.makedirs(os.path.dirname(body["answer_to"]), exist_ok=True)
        json.dump({"id": body["id"], "output": model(fake), "worker": "test"}, open(body["answer_to"], "w"))
    assert run("knowledge", "process", "--strategy", "english-notes", "--master-file", "m.json") == 0
    assert "done: vidA" in capsys.readouterr().out
    assert run("knowledge", "status") == 0
    status = capsys.readouterr().out
    assert "chunks@v1: 1 videos, 2 passages" in status and "english-notes@v1: 1 videos, 2 passages" in status


def test_ask_and_eval_with_a_model_provider(capsys):
    assert run("knowledge", "process", "--strategy", "english-notes", "--master-file", "m.json",
               "--provider", "clifake") == 0
    capsys.readouterr()
    assert run("ask", "Bukhari 5686 urine?", "--processing", "english-notes", "--provider", "clifake") == 0
    out = capsys.readouterr().out
    assert "The host cites Sahih Bukhari 5686." in out and "Urine at 00:03:00  https://youtu.be/vidA?t=180" in out

    assert run("eval", "run", "--processing", "english-notes", "--chat", "keyword", "--videos", "vidA",
               "--provider", "clifake") == 0
    out = capsys.readouterr().out
    assert "vidA-01" in out and "correct" in out and "Score 100%" in out
    assert os.path.exists("data/eval/latest/english-notes@v1__keyword@v1__clifake.json")
    assert run("eval", "compare") == 0
    assert "| english-notes@v1 | keyword@v1 | clifake | 1 | 100% | 100% | 100% | 1/0/0/0 |" in capsys.readouterr().out


def test_eval_refuses_videos_the_strategy_has_not_processed(capsys):
    with pytest.raises(SystemExit) as e:
        main(["eval", "run", "--processing", "chunks", "--chat", "keyword", "--videos", "vidA"])
    assert "has not processed vidA yet" in str(e.value.code)
