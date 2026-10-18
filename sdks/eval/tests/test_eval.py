from pathlib import Path

from seeker_sdk_chat import KeywordStrategy
from seeker_sdk_eval import (comparison_table, evaluate, keyword_score, latest_runs, load, mentions, retrieval_hit,
                             save, select)
from seeker_sdk_knowledge import KnowledgeStore, Passage
from seeker_sdk_llm import FakeProvider, Pending, ToolRunner

QUESTIONS = {
    "vidA.toml": '''video = "vidA"
[[question]]
id = "vidA-01"
question = "Which Bukhari number is cited for drinking urine?"
lang = "en"
type = "reference"
tags = []
near = "00:03:10"
answer = "Sahih Bukhari 5686."
must_mention = ["5686", "urine"]

[[question]]
id = "vidA-02"
question = "earth bed spread"
lang = "roman-ur"
type = "fact"
tags = []
near = "01:00:00"
answer = "Quran 88:20."
must_mention = ["88:20"]
''',
    "_cross.toml": '''[[question]]
id = "cross-01"
question = "Bukhari across videos"
lang = "en"
type = "cross"
tags = []
expect = [{ video = "vidA", near = "00:03:00" }, { video = "vidB", near = "00:10:00" }]
answer = "5686 and 304."
must_mention = ["5686", "304"]
''',
    "_unanswerable.toml": '''checked_against = ["vidA", "vidB"]
[[question]]
id = "none-01"
question = "What about cryptocurrency?"
lang = "en"
type = "unanswerable"
tags = []
checked_terms = ["crypto"]
answer = "Not discussed."
must_mention = []
''',
}


def write_questions(tmp_path):
    for name, text in QUESTIONS.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return load(str(tmp_path))


def test_load_and_select_by_videos(tmp_path):
    qs = write_questions(tmp_path)
    assert [q.id for q in qs] == ["cross-01", "none-01", "vidA-01", "vidA-02"]
    assert qs[0].places == [("vidA", 180.0), ("vidB", 600.0)] and qs[2].places == [("vidA", 190.0)]
    assert [q.id for q in select(qs, ["vidA"])] == ["none-01", "vidA-01", "vidA-02"]   # cross needs vidB too
    assert [q.id for q in select(qs, ["vidA", "vidB"])] == ["cross-01", "none-01", "vidA-01", "vidA-02"]
    assert [q.id for q in select(qs, ["vidA", "vidC"])] == ["vidA-01", "vidA-02"]       # vidC was never checked
    assert len(select(qs)) == 4


def test_scoring_without_a_model():
    assert mentions("sword|talwar", "the verse of the Sword") and keyword_score("Bukhari 5686", ["5686", "urine"]) == 0.5
    assert keyword_score("x", []) is None
    near = [Passage("a", "vidA", 100, 280, "t"), Passage("b", "vidB", 2000, 2100, "t")]
    assert retrieval_hit(near, [("vidA", 190.0)]) == 1.0
    assert retrieval_hit(near, [("vidA", 190.0), ("vidB", 600.0)]) == 0.5
    assert retrieval_hit([], [("vidA", 1.0)]) == 0.0 and retrieval_hit(near, []) is None


def model(request):
    if request.tool.name == "judge":
        key = request.input["reference"].split()[-1].rstrip(".")   # the reference's key number, e.g. 5686 or 88:20
        good = key in request.input["answer"]
        return {"verdict": "correct" if good else "wrong", "reason": "number matches" if good else "no number"}
    ids = [p["id"] for p in request.input["passages"]]
    if not ids:
        return {"answer": "Not found in these videos.", "citations": [], "not_found": True}
    return {"answer": "The stream cites Sahih Bukhari 5686 for drinking urine.", "citations": ids[:1], "not_found": False}


def store_with_passages(tmp_path):
    store = KnowledgeStore(str(tmp_path / "k"), "english-notes", "v1")
    store.write("vidA", [Passage("vidA#n0", "vidA", 180, 240, "The host cites Sahih Bukhari 5686: drink urine.", "A"),
                         Passage("vidA#n1", "vidA", 3500, 3700, "Quran 88:20 says the earth is spread like a bed.", "A")])
    return store


def test_evaluate_scores_and_summarises(tmp_path):
    (tmp_path / "q").mkdir()
    qs = select(write_questions(tmp_path / "q"), ["vidA"])
    run = evaluate(qs, store_with_passages(tmp_path), KeywordStrategy(k=1),
                   ToolRunner(FakeProvider(model), str(tmp_path / "cache")), videos=["vidA"])
    rows = {r.id: r for r in run.rows}
    assert rows["vidA-01"].verdict == "correct" and rows["vidA-01"].retrieval == 1.0 and rows["vidA-01"].keyword == 1.0
    assert rows["vidA-01"].citations == ["vidA#n0"] and rows["vidA-01"].retrieved == ["vidA#n0@00:03:00"]
    assert rows["vidA-02"].verdict == "wrong" and rows["vidA-02"].keyword == 0.0     # the fake gives the wrong fact
    assert rows["none-01"].verdict == "declined"                                    # nothing matched: not found
    s = run.summary
    assert (s["questions"], s["done"], s["waiting"]) == (3, 3, 0)
    assert s["score"] == 0.5 and s["retrieval"] == 1.0 and s["not_found_ok"] == 1.0 and s["declined_wrongly"] == 0
    assert s["by_lang"]["en"]["score"] == 1.0 and s["by_lang"]["roman-ur"]["score"] == 0.0
    assert run.processing == "english-notes@v1" and run.chat == "keyword@v1"


def test_waiting_rows_and_saving_and_comparing(tmp_path):
    (tmp_path / "q").mkdir()
    qs = select(write_questions(tmp_path / "q"), ["vidA"])
    run = evaluate(qs, store_with_passages(tmp_path), KeywordStrategy(k=1),
                   ToolRunner(FakeProvider(lambda r: Pending(r.id)), str(tmp_path / "cache")), videos=["vidA"])
    assert run.summary["waiting"] == 3 and run.summary["score"] is None
    latest = save(run, str(tmp_path / "eval"))
    assert latest.name == "english-notes@v1__keyword@v1__fake.json" and list((tmp_path / "eval" / "runs").glob("*.json"))
    table = comparison_table(latest_runs(str(tmp_path / "eval")))
    assert "| english-notes@v1 | keyword@v1 | fake | 0 (3 waiting) |" in table


def test_the_real_question_files_load_and_filter():
    root = Path(__file__).resolve().parents[3] / "eval" / "questions"
    qs = load(str(root))
    assert len(qs) >= 50 and len({q.id for q in qs}) == len(qs)
    two = select(qs, ["OCZ0vysB4xY", "-q9YKqT5TS4"])
    assert {q.id for q in two if q.unanswerable} == {"none-01", "none-02", "none-03"}
    assert all(set(q.videos) <= {"OCZ0vysB4xY", "-q9YKqT5TS4"} for q in two if not q.unanswerable)
