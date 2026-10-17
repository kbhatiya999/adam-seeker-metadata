"""The evaluation questions in eval/questions: format, unique ids, known videos, honest reference answers.

Checks that need a transcript (time inside the video, unanswerable topics really absent) run only where
data/transcripts has that video; transcripts are git-ignored.
"""

import json
import re
import tomllib
from pathlib import Path

import pytest

from seeker_sdk_transcripts import parse_cues

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "eval" / "questions"
TRANSCRIPTS = ROOT / "data" / "transcripts"
VIDEO_IDS = {v["video_id"] for v in json.loads((ROOT / "data" / "videos_master.json").read_text("utf-8"))["videos"]}
TYPES = {"reference", "argument", "fact", "locate", "cross", "unanswerable"}
LANGS = {"en", "roman-ur", "hi", "ur"}
TAGS = {"science-claims", "women", "prophet", "quran-history", "hadith-reliability", "violence", "jinn",
        "sexuality", "theology", "tafsir", "ex-muslim-life"}
NEAR = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def load():
    """[(file, file data, question)] for every question."""
    out = []
    for path in sorted(QUESTIONS.glob("*.toml")):
        data = tomllib.loads(path.read_text("utf-8"))
        out += [(path, data, q) for q in data.get("question", [])]
    return out


def seconds(near):
    h, m, s = map(int, near.split(":"))
    return h * 3600 + m * 60 + s


def mentions(item, text):
    return any(alt.strip().lower() in text.lower() for alt in item.split("|") if alt.strip())


def places(path, data, q):
    """(video, near) pairs a question points at."""
    if "expect" in q:
        return [(e["video"], e["near"]) for e in q["expect"]]
    if "near" in q:
        return [(data["video"], q["near"])]
    return []


ALL = load()


def test_there_are_questions_for_several_videos():
    assert len(ALL) >= 20
    assert len({p.stem for p, _, _ in ALL if not p.stem.startswith("_")}) >= 5


@pytest.mark.parametrize("path, data, q", ALL, ids=[q["id"] for _, _, q in ALL])
def test_question_format(path, data, q):
    assert q["question"].strip() and q["answer"].strip()
    assert q["lang"] in LANGS and q["type"] in TYPES
    assert set(q["tags"]) <= TAGS, set(q["tags"]) - TAGS
    assert isinstance(q["must_mention"], list)
    if q["type"] == "unanswerable":
        assert path.name == "_unanswerable.toml" and q["checked_terms"]
        assert data["checked_against"] and set(data["checked_against"]) <= VIDEO_IDS
    elif path.name == "_cross.toml":
        assert q["type"] == "cross" and len(q["expect"]) >= 2
    else:
        assert path.stem == data["video"] and data["video"] in VIDEO_IDS, "file name must be a known video id"
        assert q["id"].startswith(data["video"] + "-")
        assert q["must_mention"], "answerable questions need at least one must_mention item"
    for video, near in places(path, data, q):
        assert video in VIDEO_IDS and NEAR.match(near), (video, near)


def test_ids_are_unique():
    ids = [q["id"] for _, _, q in ALL]
    assert len(ids) == len(set(ids)), sorted(i for i in ids if ids.count(i) > 1)


@pytest.mark.parametrize("path, data, q", ALL, ids=[q["id"] for _, _, q in ALL])
def test_the_reference_answer_passes_its_own_keyword_check(path, data, q):
    missing = [item for item in q["must_mention"] if not mentions(item, q["answer"])]
    assert not missing, f"the reference answer would fail its own check: {missing}"


def test_near_lies_inside_the_video_where_the_transcript_exists():
    checked = 0
    for path, data, q in ALL:
        for video, near in places(path, data, q):
            srt = TRANSCRIPTS / f"{video}.srt"
            if srt.exists():
                assert seconds(near) < parse_cues(str(srt))[-1][1], (q["id"], video, near)
                checked += 1
    if not checked:
        pytest.skip("no transcripts in data/transcripts on this machine")


def test_unanswerable_topics_are_absent_where_the_transcript_exists():
    checked = 0
    for path, data, q in ALL:
        if q["type"] != "unanswerable":
            continue
        for video in data["checked_against"]:
            txt = TRANSCRIPTS / f"{video}.txt"
            if txt.exists():
                text = txt.read_text("utf-8")
                found = [t for t in q["checked_terms"] if t in text]
                assert not found, f"{q['id']}: {video} mentions {found}; the question is answerable now"
                checked += 1
    if not checked:
        pytest.skip("no transcripts in data/transcripts on this machine")


def test_mentions_matching():
    assert mentions("sword|talwar", "the verse of the Sword") and not mentions("5686", "Bukhari 568")
