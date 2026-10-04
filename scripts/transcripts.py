#!/usr/bin/env python3
"""
Transcript downloading for videos in the master list.

The method is chosen explicitly (--method or TRANSCRIPT_METHOD) and there is NO fallback:
if the chosen method fails, the failure is reported and nothing else is tried.

  ytdlp                   yt-dlp (optional cookies file, optional proxy URL)
  youtube_transcript_api  youtube-transcript-api (optional Webshare or generic proxy)

Two separate choices:
  --format  what yt-dlp DOWNLOADS from YouTube: ttml (default), srv1, srt or vtt. yt-dlp's `vtt` is
            YouTube's rolling-caption WebVTT (4x bigger, repeated lines), so it is not the default.
            Both methods download this same format (the library fetches it through its own session).
  --final   the FINAL files you end up with, comma separated: srt, vtt, txt (default srt,txt).
            A post-processor converts the downloaded file into these (the source is deleted unless
            --keep-source). For yt-dlp this is a real yt-dlp post-processor (TextPostProcessor).

Files are data/transcripts/<video_id>.<final> and are linked from the master list:
transcript_file (srt, else vtt, else txt), transcript_text_file (txt), transcript_downloaded,
transcript_download_date.

Optional environment (declared in fnox.toml):
  TRANSCRIPT_METHOD, TRANSCRIPT_FORMAT, TRANSCRIPT_FINAL, YTDLP_COOKIES_FILE, PROXY_URL,
  WEBSHARE_PROXY_USERNAME, WEBSHARE_PROXY_PASSWORD
"""

import argparse
import contextlib
import difflib
import glob
import json
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
import html
from typing import Dict, List, Optional, Tuple

METHODS = ('ytdlp', 'youtube_transcript_api')
TRANSCRIPT_DIR = 'data/transcripts'
SOURCE_FORMATS = ('ttml', 'srv1', 'srt', 'vtt')
FINAL_FORMATS = ('srt', 'vtt', 'txt')
SOURCE_FORMAT = 'ttml'
FINALS = ('srt', 'txt')
KEEP_SOURCE = False
LANGS = ['en']

logger = logging.getLogger('transcripts')


class TranscriptError(Exception):
    """Raised when the chosen method cannot produce a transcript."""


Cue = Tuple[float, float, str]


def _seconds(value: str) -> float:
    value = value.strip().rstrip('s')  # ttml may say "12.5s"
    if ':' not in value:
        return float(value)
    total = 0.0
    for part in value.replace(',', '.').split(':'):
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
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    cues: List[Cue] = []
    if ext == 'ttml':
        for p in ET.parse(path).getroot().iter('{http://www.w3.org/ns/ttml}p'):
            text = ' '.join(''.join(p.itertext()).split())
            if text:
                cues.append((_seconds(p.get('begin')), _seconds(p.get('end')), text))
    elif ext == 'srv1':
        for t in ET.parse(path).getroot().iter('text'):
            text = ' '.join(html.unescape(''.join(t.itertext())).split())
            start = float(t.get('start'))
            if text:
                cues.append((start, start + float(t.get('dur', '0')), text))
    else:  # srt / vtt
        with open(path, encoding='utf-8') as f:
            content = f.read().replace('\r\n', '\n')
        for block in re.split(r'\n\s*\n', content):
            lines = block.strip().split('\n')
            idx = next((i for i, line in enumerate(lines) if '-->' in line), None)
            if idx is None:
                continue
            start, end = [x.strip().split(' ')[0] for x in lines[idx].split('-->')]
            text = ' '.join(re.sub(r'<[^>]+>', '', line).strip() for line in lines[idx + 1:]).strip()
            if text:
                cues.append((_seconds(start), _seconds(end), text))
    return _merge_repeats(cues)


def _stamp(t: float, sep: str) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02}{sep}{ms:03}'


def render(cues: List[Cue], fmt: str) -> str:
    if fmt == 'txt':
        return ' '.join(text for _, _, text in cues) + '\n'
    if fmt == 'srt':
        return '\n'.join(f'{i}\n{_stamp(a, ",")} --> {_stamp(b, ",")}\n{text}\n'
                         for i, (a, b, text) in enumerate(cues, 1))
    if fmt == 'vtt':
        return 'WEBVTT\n\n' + '\n'.join(f'{_stamp(a, ".")} --> {_stamp(b, ".")}\n{text}\n' for a, b, text in cues)
    raise ValueError(f'unknown final format {fmt}')


def produce_finals(source_path: str, stem: str, finals, keep_source: bool) -> Dict[str, str]:
    """Convert a downloaded subtitle file into the final formats next to it (<stem>.<fmt>)."""
    cues = parse_cues(source_path)
    out: Dict[str, str] = {}
    for fmt in finals:
        out[fmt] = f'{stem}.{fmt}'
        with open(out[fmt], 'w', encoding='utf-8') as f:
            f.write(render(cues, fmt))
    if not keep_source and source_path not in out.values():
        os.remove(source_path)
    return out


def make_text_postprocessor(ydl):
    """yt-dlp post-processor: turn each downloaded subtitle file into the FINAL formats."""
    from yt_dlp.postprocessor import PostProcessor

    class TextPostProcessor(PostProcessor):
        def run(self, info):
            for sub in (info.get('requested_subtitles') or {}).values():
                path = sub.get('filepath')
                if path and os.path.exists(path):
                    produce_finals(path, os.path.splitext(path)[0], FINALS, KEEP_SOURCE)
            return [], info

    return TextPostProcessor(ydl)


@contextlib.contextmanager
def transcript_dir(path: str):
    """Temporarily write transcripts somewhere else (used by `compare`)."""
    global TRANSCRIPT_DIR
    old, TRANSCRIPT_DIR = TRANSCRIPT_DIR, path
    try:
        yield
    finally:
        TRANSCRIPT_DIR = old


def transcript_path(video_id: str, ext: str) -> str:
    return os.path.join(TRANSCRIPT_DIR, f'{video_id}.{ext}')


def primary_path(video_id: str) -> Optional[str]:
    """The file linked as transcript_file: srt, else vtt, else txt (whichever final exists)."""
    for ext in ('srt', 'vtt', 'txt'):
        if ext in FINALS and os.path.exists(transcript_path(video_id, ext)):
            return transcript_path(video_id, ext)
    return None


def pick_language(info: dict) -> Optional[tuple]:
    """Pick ONE caption track: (language, is_automatic).

    Asking yt-dlp for several languages (e.g. 'en.*') makes YouTube answer HTTP 429, and
    machine-translated tracks (such as 'en' on a Hindi video) are rate-limited the hardest.
    So use the video's own language: a manual track (English if there is one), otherwise the
    automatic original ('xx-orig'), otherwise automatic English, otherwise the first one.
    """
    # 'live_chat' is the chat replay of a live stream, not captions
    manual = {k: v for k, v in (info.get('subtitles') or {}).items() if k != 'live_chat'}
    auto = {k: v for k, v in (info.get('automatic_captions') or {}).items() if k != 'live_chat'}
    if manual:
        return ('en' if 'en' in manual else next(iter(manual))), False
    if auto:
        orig = next((k for k in auto if k.endswith('-orig')), None)
        if orig:
            return orig, True
        return ('en' if 'en' in auto else next(iter(auto))), True
    return None


def download_ytdlp(video_id: str, cookies_file: Optional[str], proxy: Optional[str]) -> Optional[str]:
    import yt_dlp
    if cookies_file and not os.path.exists(cookies_file):
        raise TranscriptError(f'Cookies file not found: {cookies_file}')
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    url = f'https://www.youtube.com/watch?v={video_id}'
    base = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    if cookies_file:
        base['cookiefile'] = cookies_file
    if proxy:
        base['proxy'] = proxy
    try:
        with yt_dlp.YoutubeDL(base) as ydl:
            info = ydl.extract_info(url, download=False)
        choice = pick_language(info)
        if not choice:
            return None
        lang, is_auto = choice
        logger.info('%s: using %s captions in %s', video_id, 'automatic' if is_auto else 'manual', lang)
        opts = dict(base, writesubtitles=not is_auto, writeautomaticsub=is_auto, subtitleslangs=[lang],
                    subtitlesformat=SOURCE_FORMAT, outtmpl=os.path.join(TRANSCRIPT_DIR, '%(id)s'))
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.add_post_processor(make_text_postprocessor(ydl), when='before_dl')
            ydl.download([url])
    except Exception as e:
        raise TranscriptError(f'yt-dlp failed: {e}') from e
    # yt-dlp names files <id>.<lang>.<ext>; normalise every file we keep to <id>.<ext>
    kept = list(FINALS) + ([SOURCE_FORMAT] if KEEP_SOURCE else [])
    got_any = False
    for ext in dict.fromkeys(kept):
        found = sorted(glob.glob(os.path.join(TRANSCRIPT_DIR, f'{video_id}.*.{ext}')))
        if not found:
            continue
        got_any = True
        os.replace(found[0], transcript_path(video_id, ext))
        for extra in found[1:]:
            os.remove(extra)
    return primary_path(video_id) if got_any else None


def _transcript_api(proxy: Optional[str], ws_user: Optional[str], ws_pass: Optional[str]):
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig
    if ws_user and ws_pass:
        return YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(proxy_username=ws_user, proxy_password=ws_pass))
    if proxy:
        return YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=proxy, https_url=proxy))
    return YouTubeTranscriptApi()


def download_transcript_api(video_id: str, proxy: Optional[str], ws_user: Optional[str],
                            ws_pass: Optional[str]) -> Optional[str]:
    """Download with youtube-transcript-api, in the SAME source format as yt-dlp (default ttml).

    The library normally returns parsed snippets only. Each Transcript object knows its timedtext
    URL and the configured (proxy-aware) HTTP session, so we request that URL with &fmt=<format>
    (YouTube serves ttml, srv1, srt and vtt) and keep the raw file, like yt-dlp does.
    """
    api = _transcript_api(proxy, ws_user, ws_pass)
    try:
        transcripts = list(api.list(video_id))
        if not transcripts:
            return None
        chosen = next((t for t in transcripts if t.language_code in LANGS), transcripts[0])
        if not (hasattr(chosen, '_url') and hasattr(chosen, '_http_client')):
            raise TranscriptError('youtube-transcript-api changed its internals; update scripts/transcripts.py')
        if '&exp=xpe' in chosen._url:
            raise TranscriptError('YouTube requires a PO token for this video (not supported)')
        response = chosen._http_client.get(f'{chosen._url}&fmt={SOURCE_FORMAT}')
        response.raise_for_status()
    except TranscriptError:
        raise
    except Exception as e:
        raise TranscriptError(f'youtube-transcript-api failed: {e}') from e
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    source = transcript_path(video_id, f'source.{SOURCE_FORMAT}')
    with open(source, 'wb') as f:
        f.write(response.content)
    produce_finals(source, os.path.join(TRANSCRIPT_DIR, video_id), FINALS, KEEP_SOURCE)
    return primary_path(video_id)


def check_available(video_id: str, method: str, env: Dict[str, Optional[str]]) -> bool:
    """True if the chosen method can see a transcript (does not download)."""
    try:
        if method == 'ytdlp':
            import yt_dlp
            opts = {'quiet': True, 'skip_download': True}
            if env['cookies']:
                opts['cookiefile'] = env['cookies']
            if env['proxy']:
                opts['proxy'] = env['proxy']
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
            return bool(info.get('subtitles') or info.get('automatic_captions'))
        api = _transcript_api(env['proxy'], env['ws_user'], env['ws_pass'])
        return any(True for _ in api.list(video_id))
    except Exception as e:
        raise TranscriptError(f'{method} availability check failed: {e}') from e


def download(video_id: str, method: str, env: Dict[str, Optional[str]]) -> Optional[str]:
    if method == 'ytdlp':
        return download_ytdlp(video_id, env['cookies'], env['proxy'])
    return download_transcript_api(video_id, env['proxy'], env['ws_user'], env['ws_pass'])


class Master:
    def __init__(self, path: str):
        self.path = path
        with open(path, encoding='utf-8') as f:
            self.data = json.load(f)

    def save(self) -> None:
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def missing(self) -> List[Dict]:
        return [v for v in self.data.get('videos', [])
                if not (v.get('transcript_file') and os.path.exists(v['transcript_file']))]

    def link(self, video_id: str, path: str) -> None:
        for v in self.data['videos']:
            if v['video_id'] == video_id:
                v['transcript_file'] = path
                txt = os.path.splitext(path)[0] + '.txt'
                if os.path.exists(txt):
                    v['transcript_text_file'] = txt
                v['transcript_downloaded'] = True
                v['transcript_download_date'] = datetime.now().isoformat()[:10]
                return
        raise TranscriptError(f'Video {video_id} not in master list')


def compare(video_id: str, env: Dict[str, Optional[str]]) -> int:
    """Run both methods independently (no fallback) into data/transcripts/compare/<id>/<method>/
    and print how they differ. The master list is not touched."""
    rows, results = [], {}
    for method in METHODS:
        out_dir = os.path.join(TRANSCRIPT_DIR, 'compare', video_id, method)
        os.makedirs(out_dir, exist_ok=True)
        try:
            with transcript_dir(out_dir):
                path = download(video_id, method, env)
        except TranscriptError as e:
            rows.append((method, 'FAILED', str(e).strip().splitlines()[0][:70], '', '', ''))
            continue
        if not path:
            rows.append((method, 'none', 'no transcript available', '', '', ''))
            continue
        folder = os.path.dirname(path)
        files = [(ext, os.path.join(folder, f'{video_id}.{ext}')) for ext in FINALS
                 if os.path.exists(os.path.join(folder, f'{video_id}.{ext}'))]
        words = len(' '.join(text for _, _, text in parse_cues(path)).split())
        results[method] = files
        rows.append((method, 'ok', f'{os.path.getsize(path) // 1024} KB {os.path.splitext(path)[1][1:]}',
                     f'{words} words', '', ''))
    print(f'\nCompare for {video_id}  (downloaded as {SOURCE_FORMAT}, final: {",".join(FINALS)})')
    for method, status, a, b, c, d in rows:
        print(f'  {method:<24} {status:<7} {a}  {b}')
        for ext, p in results.get(method, ()):
            print(f'  {"":<24}         {ext}: {p}')
    if len(results) == len(METHODS):
        print('\n  Diff of the final files (ytdlp vs youtube_transcript_api):')
        first, second = METHODS
        for ext, path_a in results[first]:
            path_b = dict(results[second]).get(ext)
            with open(path_a, encoding='utf-8') as fa, open(path_b, encoding='utf-8') as fb:
                lines_a, lines_b = fa.read().splitlines(), fb.read().splitlines()
            if lines_a == lines_b:
                print(f'    {ext}: identical ({len(lines_a)} lines, byte for byte: '
                      f'{open(path_a, "rb").read() == open(path_b, "rb").read()})')
                continue
            diff = [d for d in difflib.unified_diff(lines_a, lines_b, first, second, lineterm='', n=0)
                    if not d.startswith(('---', '+++', '@@'))]
            print(f'    {ext}: DIFFERENT, {len(diff)} changed lines ({len(lines_a)} vs {len(lines_b)} lines)')
            for d in diff[:6]:
                print('      ' + d[:110])
    return 0 if len(results) == len(METHODS) else 1


def resolve_method(arg: Optional[str]) -> str:
    method = arg or os.getenv('TRANSCRIPT_METHOD')
    if method not in METHODS:
        sys.exit(f"Choose a method with --method or TRANSCRIPT_METHOD: one of {', '.join(METHODS)} "
                 f"(got {method!r}). There is no default and no fallback.")
    return method


def read_env() -> Dict[str, Optional[str]]:
    return {
        'cookies': os.getenv('YTDLP_COOKIES_FILE') or None,
        'proxy': os.getenv('PROXY_URL') or None,
        'ws_user': os.getenv('WEBSHARE_PROXY_USERNAME') or None,
        'ws_pass': os.getenv('WEBSHARE_PROXY_PASSWORD') or None,
    }


def main() -> int:
    p = argparse.ArgumentParser(description='Download and manage video transcripts')
    p.add_argument('--master-file', default='data/videos_master.json')
    p.add_argument('--method', choices=METHODS, help='transcript method (or set TRANSCRIPT_METHOD)')
    p.add_argument('--format', choices=SOURCE_FORMATS,
                   help='format DOWNLOADED from YouTube by either method (or TRANSCRIPT_FORMAT; default ttml)')
    p.add_argument('--final', help='FINAL formats, comma separated from srt,vtt,txt (or TRANSCRIPT_FINAL; default srt,txt)')
    p.add_argument('--keep-source', action='store_true', help='also keep the downloaded file')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('stats', help='Show how many videos have transcripts')
    lm = sub.add_parser('list-missing', help='List videos without a transcript')
    lm.add_argument('--limit', type=int, default=20)
    dm = sub.add_parser('download-missing', help='Download transcripts for videos that lack one')
    dm.add_argument('--limit', type=int, default=10, help='max videos this run (default 10)')
    d1 = sub.add_parser('download', help='Download the transcript for one video')
    d1.add_argument('video_id')
    c1 = sub.add_parser('check', help='Check whether a transcript is available for one video')
    c1.add_argument('video_id')
    cp = sub.add_parser('compare', help='Download one video with BOTH methods side by side (nothing is linked)')
    cp.add_argument('video_id')
    args = p.parse_args()

    global SOURCE_FORMAT, FINALS, KEEP_SOURCE
    fmt = args.format or os.getenv('TRANSCRIPT_FORMAT') or SOURCE_FORMAT
    if fmt not in SOURCE_FORMATS:
        sys.exit(f'--format must be one of {", ".join(SOURCE_FORMATS)} (got {fmt!r})')
    finals = tuple(dict.fromkeys(x.strip() for x in (args.final or os.getenv('TRANSCRIPT_FINAL') or ','.join(FINALS)).split(',') if x.strip()))
    bad = [x for x in finals if x not in FINAL_FORMATS]
    if bad or not finals:
        sys.exit(f'--final must be a comma separated list from {", ".join(FINAL_FORMATS)} (got {bad or "nothing"})')
    SOURCE_FORMAT, FINALS, KEEP_SOURCE = fmt, finals, args.keep_source

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    master = Master(args.master_file)

    if args.cmd == 'stats':
        total = len(master.data.get('videos', []))
        missing = len(master.missing())
        print(f'Videos: {total}  with transcript: {total - missing}  missing: {missing}')
        return 0
    if args.cmd == 'list-missing':
        for v in master.missing()[:args.limit]:
            print(f"{v['video_id']}  {v.get('upload_date', '')}  {v.get('title', '')[:70]}")
        return 0

    if args.cmd == 'compare':
        return compare(args.video_id, read_env())

    method, env = resolve_method(args.method), read_env()
    logger.info('Method: %s (no fallback); download format: %s; final: %s',
                method, SOURCE_FORMAT, ','.join(FINALS))

    if args.cmd == 'check':
        print('available' if check_available(args.video_id, method, env) else 'not available')
        return 0

    ids = [args.video_id] if args.cmd == 'download' else [v['video_id'] for v in master.missing()[:args.limit]]
    ok = failed = 0
    for vid in ids:
        try:
            path = download(vid, method, env)
        except TranscriptError as e:
            logger.error('%s: %s', vid, e)
            failed += 1
            continue
        if not path:
            logger.warning('%s: no transcript available', vid)
            failed += 1
            continue
        try:
            master.link(vid, path)
            master.save()
        except TranscriptError as e:
            logger.warning('%s: transcript saved to %s but %s', vid, path, e)
        else:
            logger.info('%s: saved %s', vid, path)
        ok += 1
    print(f'Done: {ok} downloaded, {failed} failed/unavailable')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
