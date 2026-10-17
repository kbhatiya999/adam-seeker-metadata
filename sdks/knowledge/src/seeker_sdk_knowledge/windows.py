"""Cut a transcript (.srt) into time windows, keeping timestamps the model can cite."""

from typing import List, Tuple

from seeker_sdk_transcripts import parse_cues

from .model import hms

Window = Tuple[float, float, List[Tuple[float, str]]]  # start, end, [(cue start, text)]


def windows(srt_path: str, seconds: float) -> List[Window]:
    cues = parse_cues(srt_path)
    out: List[Window] = []
    for start, _end, text in cues:
        index = int(start // seconds)
        while len(out) <= index:
            out.append((len(out) * seconds, (len(out) + 1) * seconds, []))
        out[index][2].append((start, text))
    last = cues[-1][1] if cues else 0.0
    return [(s, min(e, last), lines) for s, e, lines in out if lines]


def timed_text(lines: List[Tuple[float, str]], every: float = 20.0) -> str:
    """Join cues into lines of about `every` seconds, each starting with [HH:MM:SS]."""
    out, current, current_start = [], [], None
    for start, text in lines:
        if current_start is None:
            current_start = start
        if start - current_start >= every and current:
            out.append(f"[{hms(current_start)}] " + " ".join(current))
            current, current_start = [], start
        current.append(text)
    if current:
        out.append(f"[{hms(current_start)}] " + " ".join(current))
    return "\n".join(out)


def plain_text(lines: List[Tuple[float, str]]) -> str:
    return " ".join(text for _, text in lines)
