import json

from seeker_chat import core
from seeker_sdk_knowledge import KnowledgeStore, Passage
from seeker_sdk_llm import FakeProvider, Pending, Waiting


def repo(tmp_path):
    notes = KnowledgeStore(str(tmp_path / "data" / "knowledge"), "english-notes", "v1")
    notes.write("vidA", [Passage("vidA#n0000", "vidA", 1471, 1500, "The host reads Quran 13:2 about pillars.", "Earth")])
    KnowledgeStore(str(tmp_path / "data" / "knowledge"), "chunks", "v1").write(
        "vidA", [Passage("vidA#c0000", "vidA", 0, 180, "सूरह रात", "Earth")])
    (tmp_path / "data" / "eval" / "latest").mkdir(parents=True)
    (tmp_path / "data" / "eval" / "latest" / "x.json").write_text(json.dumps(
        {"processing": "english-notes@v1", "chat": "keyword@v1", "provider": "queue", "summary": {"score": 0.83}}))
    (tmp_path / "data" / "eval" / "latest" / "y.json").write_text(json.dumps(
        {"processing": "english-notes@v1", "chat": "keyword@v1", "provider": "gemini/m",
         "summary": {"score": 1.0, "questions": 15, "done": 9, "waiting": 6}}))
    (tmp_path / "eval" / "questions").mkdir(parents=True)
    (tmp_path / "eval" / "questions" / "vidA.toml").write_text('''video = "vidA"
[[question]]
id = "vidA-01"
question = "Which Quran verse is used to say that Allah raised the heavens without pillars you can see?"
lang = "en"
type = "reference"
tags = []
near = "00:24:31"
answer = "13:2"
must_mention = ["13:2"]
''')
    return tmp_path


def test_pairs_put_english_notes_first_with_labels_and_scores(tmp_path):
    found = core.pairs(repo(tmp_path))
    assert [p.name for p in found] == ["english-notes@v1+keyword", "english-notes@v1+multilingual",
                                       "chunks@v1+keyword", "chunks@v1+multilingual"]
    best = found[0]
    assert best.label == "English notes + keyword search" and best.videos == ("vidA",)
    assert "83% (queue)" in best.description and "100% (gemini/m, 9 of 15 questions)" in best.description
    assert "1 processed video" in best.description
    assert core.find(tmp_path, "chunks@v1+keyword").label == "Raw captions + keyword search"
    assert core.find(tmp_path, None) == best and core.pairs(tmp_path / "empty") == []


def test_starters_come_from_the_evaluation_questions_of_processed_videos(tmp_path):
    [(label, question)] = core.starters(repo(tmp_path), core.pairs(tmp_path)[0])
    assert question.startswith("Which Quran verse") and label.endswith("...") and len(label) <= 63


def model(request):
    if request.tool.name == "answer":
        return {"answer": "The host reads Quran 13:2.", "citations": [request.input["passages"][0]["id"]], "not_found": False}
    return {"queries": [request.input["question"]]}


def test_answer_with_sources_and_search_details(tmp_path):
    root = repo(tmp_path)
    result, runner = core.answer("Quran 13:2 pillars?", core.pairs(root)[0], "key", root,
                                 provider_factory=lambda key, m: FakeProvider(model))
    text = core.format_answer(result)
    assert text.startswith("The host reads Quran 13:2.") and "**Sources**" in text
    assert "1. [Earth at 00:24:31](https://youtu.be/vidA?t=1471)" in text
    assert "Searched with: Quran 13:2 pillars?" in core.search_details(result)
    assert list((root / "data" / "llm" / "cache" / "fake").iterdir())   # cached with the CLI's cache


def test_waiting_explains_the_quota_and_what_to_do(tmp_path):
    root = repo(tmp_path)
    result, runner = core.answer("q", core.pairs(root)[0], "key", root,
                                 provider_factory=lambda key, m: FakeProvider(lambda r: Pending(r.id, "daily quota used up")))
    assert isinstance(result, Waiting)
    text = core.waiting_text(runner)
    assert "daily quota used up" in text and "pick another model" in text
    assert core.KEY_URL in core.NO_KEY and "not saved on the server" in core.NO_KEY
