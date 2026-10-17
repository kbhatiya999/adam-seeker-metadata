# Evaluation results

## 2026-10-18: first comparison (2 videos, 15 questions)
Videos: `OCZ0vysB4xY` (flat earth, 6 h, Devanagari captions) and `-q9YKqT5TS4` (Quran history debate, 1 h, Bengali
script). 12 answerable questions (10 English, 2 Roman Urdu) and 3 unanswerable. The "model" for every tool
(notes, query rewriting, answers, judging) was disposable Claude Haiku subagents answering the file queue, standing
in for Gemini Flash. `seeker eval compare`:

| processing | chat | score | retrieval | keywords | correct/partial/wrong/declined | not found ok | en | roman-ur |
|---|---|---|---|---|---|---|---|---|
| english-notes@v1 | keyword@v1 | 83% | 92% | 89% | 9/2/0/1 | 100% | 90% | 50% |
| english-notes@v1 | multilingual@v1 | 75% | 75% | 90% | 8/2/1/1 | 100% | 75% | 75% |
| chunks@v1 | multilingual@v1 | 50% | 50% | 85% | 4/4/1/3 | 100% | 55% | 25% |
| chunks@v1 | keyword@v1 | 17% | 17% | 33% | 2/0/0/10 | 100% | 20% | 0% |

What it shows:
- **The script problem is real.** English keywords against raw Devanagari/Bengali captions found the right
  passage for 2 of 12 questions (chunks + keyword).
- **Fixing the query helps; fixing the data helps more.** Rewriting the question into several scripts triples the
  score on raw captions (50%), and English notes reach 83% with plain keyword search.
- **Rewriting hurts English questions on English notes** (90% to 75%: the extra Devanagari/Roman keywords dilute
  the search) **but helps Roman Urdu questions** (50% to 75%). Candidate `v2` chat strategy: rewrite only when
  the question is not in English, or weight the original question higher.
- **Attribution is the weak spot of `english-notes@v1`.** Notes sometimes give a position argued about in the
  debate to "the host", and the one wrong answer on notes mixed up whose standard was being stated. Candidate
  `english_notes@v2` prompt: say "presented as what the Quran says" when a position is put forward for argument,
  and mark speakers `unknown` more readily.

Caveats: a small sample (one question is 8 points); the judge is the same model family as the answerer; the
query-rewriting worker added verse numbers it knew (13:2, 88:20 ...) to the search keywords, which helps
retrieval; Haiku is a stand-in, so Gemini's numbers will differ. Cost: 16 subagent runs, about 2.5 M subagent
tokens; 141 tool answers cached, 0 rejected.
