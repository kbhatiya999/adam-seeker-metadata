# Evaluation questions

These questions measure how well a processing strategy plus a chat strategy answers questions about the
channel. Every strategy pair gets the same questions, so the scores can be compared.

## Point of view
The questions are the kind an ex-Muslim activist or researcher would ask when using the channel as a source:
- which verse, hadith or tafsir is cited for a claim, and its number
- what argument or critique is made, and what the other side answers
- where (which video, roughly when) something is said
- what comes up across several videos (all the Bukhari numbers cited, everything said about women)

The questions are asked in English and in Roman Urdu or Hindi, because people ask both ways and the transcripts
are in a third form: Devanagari, with English words written phonetically, and one video in Bengali script.

The reference answers describe **what is said in the video**, attributed to the stream, a participant or a caller.
They are not statements of fact about Islam, and an answer is scored on matching the video, not on agreeing with it.

## Files
- `questions/<video_id>.toml`: questions answered by one video (the file name is the video id)
- `questions/_cross.toml`: answers spread over several videos
- `questions/_unanswerable.toml`: topics these videos do not discuss; the right answer is "not found"

| Field | Meaning |
|---|---|
| `id` | unique; per-video questions start with the video id |
| `question` | as a user would type it |
| `lang` | `en`, `roman-ur` (Roman Urdu/Hindi), `hi`, `ur` |
| `type` | `reference` (which verse/hadith), `argument`, `fact`, `locate`, `cross`, `unanswerable` |
| `tags` | topic: `science-claims`, `women`, `prophet`, `quran-history`, `hadith-reliability`, `violence`, `jinn`, `sexuality`, `theology`, `tafsir`, `ex-muslim-life` |
| `near` | where the answer starts in the video (`HH:MM:SS`); counts as found within 3 minutes |
| `expect` | (cross) list of `{ video, near }` |
| `answer` | short reference answer |
| `must_mention` | items a good answer contains. Each item is a list of alternatives separated by `\|`, case-insensitive (`"5686"`, `"sword\|talwar"`) |
| `checked_against`, `checked_terms` | (unanswerable) the videos searched and the words searched for |

## How it is scored (`seeker-sdk-eval`, `seeker eval run`)
- **Retrieval:** is the expected video, within 3 minutes of `near`, among the passages the strategy retrieved?
- **Keywords:** the share of `must_mention` items in the answer. This is cheap and needs no model call.
- **Judge:** a model (tool `judge@v1`) compares the answer with the reference: correct, partial, wrong or declined.
  `--no-judge` skips it.
- **Not found:** unanswerable questions must be declined. They only count when the evaluation is limited to
  `checked_against` (or a subset), because a video added later might discuss the topic.
- **Cost:** requests and tokens used.

Evaluations can be limited to videos, for example
`seeker eval run --processing english-notes --chat keyword --videos OCZ0vysB4xY,c8xpAqtScUQ`.
Processing takes the same filter (`seeker knowledge process --videos ...`), so quota is only spent on the videos being
evaluated. `seeker eval compare` shows the latest run of every pair.

Results so far, with what they show and their caveats: `RESULTS.md`.

## How these were written (2026-10-18)
Each video's transcript (`data/transcripts/<id>.srt`, yt-dlp automatic captions) was read in timed windows and
searched for references (surah, ayat, Bukhari, Muslim, tafsir, Ibn Kathir). Every question points at a passage
that was read, and numbers are given as they were heard. The captions can mishear: one hadith is given as
"68", probably 608, and the question says so. The live streams have many speakers, so answers say "the stream"
or "a participant" unless it is clear who speaks.

## Adding questions
1. Pick a video that has a transcript (`seeker transcripts list-missing` shows those that do not).
2. Read the passage in `data/transcripts/<id>.srt` and note the time.
3. Add a `[[question]]` to `questions/<id>.toml` (create the file with `video`, `title`, `transcript`, `written`).
4. Run `mise run test`. `scripts/tests/test_eval_questions.py` checks the format, unique ids and known videos,
   that the reference answer passes its own `must_mention`, that `near` lies inside the video, and that
   unanswerable topics really are absent (the last two only where the transcript exists locally).
