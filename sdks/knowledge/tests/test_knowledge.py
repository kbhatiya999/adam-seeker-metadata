import json

from seeker_sdk_core import MasterList
from seeker_sdk_knowledge import (ChunksStrategy, EnglishNotesStrategy, KnowledgeStore, get_strategy, process,
                                  strategy_names, timed_text, windows)
from seeker_sdk_llm import FakeProvider, Pending, QueueProvider, ToolRunner


def srt(path, cues):
    blocks = []
    for i, (start, text) in enumerate(cues, 1):
        a, b = start, start + 5
        stamp = lambda s: f"{s // 3600:02}:{s % 3600 // 60:02}:{s % 60:02},000"  # noqa: E731
        blocks.append(f"{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def setup(tmp_path):
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    srt(tdir / "vid1.srt", [(0, "कुरान 13:2"), (30, "पिलर्स"), (200, "जमीन बिछा दी"), (1000, "सूरह 88")])
    master = MasterList(str(tmp_path / "m.json"), {"videos": [
        {"video_id": "vid1", "title": "Earth"}, {"video_id": "vid2", "title": "No transcript"}]})
    return master, str(tdir)


def notes_for(request):
    window = request.input["window"]["start"]
    if window == "00:00:00":
        return {"notes": [{"start": "00:00:30", "kind": "reference", "speaker": "host", "text": "The host reads Quran 13:2.",
                           "refs": ["Quran 13:2"], "topics": ["flat earth"]},
                          {"start": "99:00:00", "kind": "claim", "speaker": "caller", "text": "A caller disagrees."}]}
    return {"notes": [{"start": "bad", "kind": "argument", "speaker": "unknown", "text": "Spread out like a bed."}]}


def test_windows_and_timed_text(tmp_path):
    master, tdir = setup(tmp_path)
    w = windows(f"{tdir}/vid1.srt", 180)
    assert [(s, len(lines)) for s, _, lines in w] == [(0, 2), (180, 1), (900, 1)]  # empty windows are dropped
    assert timed_text(w[0][2], every=20).splitlines() == ["[00:00:00] कुरान 13:2", "[00:00:30] पिलर्स"]


def test_chunks_strategy_writes_passages_and_skips_done_videos(tmp_path):
    master, tdir = setup(tmp_path)
    store = KnowledgeStore(str(tmp_path / "k"), "chunks", "v1")
    report = process(ChunksStrategy(), master, store, transcripts_dir=tdir, videos=["vid1", "vid2"])
    assert report.done == ["vid1"] and report.no_transcript == ["vid2"]
    passages = store.passages()
    assert [p.id for p in passages] == ["vid1#c0000", "vid1#c0001", "vid1#c0002"] and passages[0].title == "Earth"
    assert passages[0].text == "कुरान 13:2 पिलर्स" and passages[1].link == "https://youtu.be/vid1?t=180"
    assert store.manifest()["videos"]["vid1"]["passages"] == 3 and store.manifest()["settings"] == {"window_seconds": 180}
    assert process(ChunksStrategy(), master, store, transcripts_dir=tdir).skipped == ["vid1"]
    assert store.passages(videos=["other"]) == []


def test_english_notes_waits_for_the_model_then_writes_notes(tmp_path):
    master, tdir = setup(tmp_path)
    store = KnowledgeStore(str(tmp_path / "k"), "english-notes", "v1")
    queue = QueueProvider(str(tmp_path / "q"))
    report = process(EnglishNotesStrategy(), master, store, ToolRunner(queue, str(tmp_path / "c")), transcripts_dir=tdir)
    assert report.waiting == {"vid1": 2} and not store.has("vid1") and queue.status()["pending"] == 2

    for path in queue.pending_files("english_notes"):   # a worker answers the queue
        body = json.loads(open(path, encoding="utf-8").read())
        assert "[00:00:00] कुरान 13:2" in body["input"]["transcript"] or body["input"]["window"]["start"] == "00:15:00"
        fake = type("R", (), {"input": body["input"]})
        done = tmp_path / "q" / "done" / f"{body['id']}.json"
        done.parent.mkdir(parents=True, exist_ok=True)
        done.write_text(json.dumps({"id": body["id"], "output": notes_for(fake)}), encoding="utf-8")

    report = process(EnglishNotesStrategy(), master, store, ToolRunner(queue, str(tmp_path / "c")), transcripts_dir=tdir)
    assert report.done == ["vid1"] and queue.status() == {"pending": 0, "done": 0, "rejected": 0}
    notes = store.passages()
    assert [n.when for n in notes] == ["00:00:30", "00:15:00", "00:15:00"]   # bad time -> window start; 99h -> clamped
    first = notes[0]
    assert first.kind == "reference" and first.meta == {"speaker": "host", "refs": ["Quran 13:2"], "topics": ["flat earth"]}
    assert first.text == "The host reads Quran 13:2. References: Quran 13:2. Topics: flat earth."
    md = (store.dir / "notes" / "vid1.md").read_text(encoding="utf-8")
    assert "[00:00:30](https://youtu.be/vid1?t=30) **host, reference**" in md


def test_english_notes_with_a_fake_model_in_one_go(tmp_path):
    master, tdir = setup(tmp_path)
    store = KnowledgeStore(str(tmp_path / "k"), "english-notes", "v1")
    provider = FakeProvider(notes_for)
    report = process(EnglishNotesStrategy(), master, store, ToolRunner(provider, str(tmp_path / "c")), transcripts_dir=tdir)
    assert report.done == ["vid1"] and len(provider.calls) == 2
    provider2 = FakeProvider(lambda r: Pending(r.id))
    # cached answers are reused: a forced re-run does not ask the model again
    report = process(EnglishNotesStrategy(), master, store, ToolRunner(provider2, str(tmp_path / "c")),
                     transcripts_dir=tdir, force=True)
    assert report.done == ["vid1"] and provider2.calls == []


def test_strategies_are_plugins():
    assert {"chunks", "english-notes"} <= set(strategy_names())
    assert isinstance(get_strategy("chunks", window_seconds=60), ChunksStrategy)
    assert get_strategy("english-notes").uses_llm
