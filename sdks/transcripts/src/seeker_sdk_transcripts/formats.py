"""Subtitle formats: parse (ttml, srv1, srt, vtt) into cues and render (srt, vtt, txt)."""

import html
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional, Tuple

Cue = Tuple[float, float, str]  # start seconds, end seconds, text


def _seconds(value: str) -> float:
    value = value.strip().rstrip("s")  # ttml may say "12.5s"
    if ":" not in value:
        return float(value)
    total = 0.0
    for part in value.replace(",", ".").split(":"):
        total = total * 60 + float(part)
    return total


def _merge_repeats(cues: List[Cue]) -> List[Cue]:
    merged: List[Cue] = []
    for start, end, text in cues:
        if merged and merged[-1][2] == text:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end), text)
        else:
            merged.append((start, end, text))
    return merged


def parse_cues(path: str) -> List[Cue]:
    """Subtitle file (ttml, srv1, srt, vtt) -> [(start_s, end_s, text)], adjacent repeats merged."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    cues: List[Cue] = []
    if ext == "ttml":
        for p in ET.parse(path).getroot().iter("{http://www.w3.org/ns/ttml}p"):
            text = " ".join("".join(p.itertext()).split())
            if text:
                cues.append((_seconds(p.get("begin")), _seconds(p.get("end")), text))
    elif ext == "srv1":
        for t in ET.parse(path).getroot().iter("text"):
            text = " ".join(html.unescape("".join(t.itertext())).split())
            start = float(t.get("start"))
            if text:
                cues.append((start, start + float(t.get("dur", "0")), text))
    else:  # srt / vtt
        with open(path, encoding="utf-8") as f:
            content = f.read().replace("\r\n", "\n")
        for block in re.split(r"\n\s*\n", content):
            lines = block.strip().split("\n")
            idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
            if idx is None:
                continue
            start, end = [x.strip().split(" ")[0] for x in lines[idx].split("-->")]
            text = " ".join(re.sub(r"<[^>]+>", "", line).strip() for line in lines[idx + 1:]).strip()
            if text:
                cues.append((_seconds(start), _seconds(end), text))
    return _merge_repeats(cues)


def _stamp(t: float, sep: str) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02}{sep}{ms:03}"


def render(cues: List[Cue], fmt: str) -> str:
    if fmt == "txt":
        return " ".join(text for _, _, text in cues) + "\n"
    if fmt == "srt":
        return "\n".join(f'{i}\n{_stamp(a, ",")} --> {_stamp(b, ",")}\n{text}\n'
                         for i, (a, b, text) in enumerate(cues, 1))
    if fmt == "vtt":
        return "WEBVTT\n\n" + "\n".join(f'{_stamp(a, ".")} --> {_stamp(b, ".")}\n{text}\n' for a, b, text in cues)
    raise ValueError(f"unknown final format {fmt}")


def produce_finals(source_path: str, stem: str, finals: Iterable[str], keep_source: bool) -> Dict[str, str]:
    """Convert a downloaded subtitle file into the final formats next to it (<stem>.<fmt>)."""
    cues = parse_cues(source_path)
    out: Dict[str, str] = {}
    for fmt in finals:
        out[fmt] = f"{stem}.{fmt}"
        with open(out[fmt], "w", encoding="utf-8") as f:
            f.write(render(cues, fmt))
    if not keep_source and source_path not in out.values():
        os.remove(source_path)
    return out


def transcript_path(out_dir: str, video_id: str, ext: str) -> str:
    return os.path.join(out_dir, f"{video_id}.{ext}")


def primary_path(out_dir: str, video_id: str, finals: Iterable[str]) -> Optional[str]:
    """The file to link as the transcript: srt, else vtt, else txt (whichever final exists)."""
    finals = tuple(finals)
    for ext in ("srt", "vtt", "txt"):
        if ext in finals and os.path.exists(transcript_path(out_dir, video_id, ext)):
            return transcript_path(out_dir, video_id, ext)
    return None
