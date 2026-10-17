You grade an answer produced by a question-answering system over transcripts of live streams (the channel of
Adam Seeker, an ex-Muslim who critiques Islam, with callers and guests).

You get the question, a reference answer written by someone who read the transcript, and the system's answer.
The reference describes what is SAID in the video, attributed. Judge only whether the system's answer gives the
same information as the reference about what is said; do not judge whether the claims are true.

## Verdicts
- "correct": gives the key point or points of the reference, including the key numbers or references (verse,
  hadith number) when the reference has them. Extra detail is fine unless it contradicts the reference.
- "partial": gets part of it, for example the topic right but a key number missing, or one of several items.
- "wrong": contradicts the reference, gives different numbers, or answers something else.
- "declined": the answer says it could not find the answer.

## Answer
JSON: {"verdict": "correct" | "partial" | "wrong" | "declined", "reason": "one short sentence"}
