#!/usr/bin/env python3
"""
Transcript downloading for videos in the master list.

The method is chosen explicitly (--method or TRANSCRIPT_METHOD) and there is NO fallback:
if the chosen method fails, the failure is reported and nothing else is tried.

  ytdlp                   yt-dlp (optional cookies file, optional proxy URL)
  youtube_transcript_api  youtube-transcript-api (optional Webshare or generic proxy)

Each transcript is saved as data/transcripts/<video_id>.<format> (default srt) plus a plain-text
<video_id>.txt, and linked from the master list (transcript_file, transcript_text_file,
transcript_downloaded, transcript_download_date).

Format (--format or TRANSCRIPT_FORMAT): srt (default), srv1, ttml, vtt. yt-dlp's `vtt` is YouTube's
rolling-caption WebVTT: ~4x bigger with repeated lines, so it is not the default. srv1 and ttml
are yt-dlp only; youtube_transcript_api supports srt and vtt. With yt-dlp the .txt is produced by
a yt-dlp post-processor (TextPostProcessor).

Optional environment (declared in fnox.toml):
  TRANSCRIPT_METHOD, TRANSCRIPT_FORMAT, YTDLP_COOKIES_FILE, PROXY_URL,
  WEBSHARE_PROXY_USERNAME, WEBSHARE_PROXY_PASSWORD
"""

import argparse
import contextlib
import glob
import json
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional

METHODS = ('ytdlp', 'youtube_transcript_api')
TRANSCRIPT_DIR = 'data/transcripts'
FORMATS = ('srt', 'srv1', 'ttml', 'vtt')
TRANSCRIPT_FORMAT = 'srt'
LANGS = ['en']

logger = logging.getLogger('transcripts')


class TranscriptError(Exception):
    """Raised when the chosen method cannot produce a transcript."""


def to_plain_text(path: str) -> str:
    """Subtitle file (srt, vtt, srv1, ttml) -> running text without timestamps or repeated lines."""
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    if ext in ('srv1', 'ttml'):
        root = ET.parse(path).getroot()
        tag = 'text' if ext == 'srv1' else '{http://www.w3.org/ns/ttml}p'
        raw = [' '.join(''.join(el.itertext()).split()) for el in root.iter(tag)]
    else:  # srt / vtt
        raw = []
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if (not line or line == 'WEBVTT' or line.startswith(('Kind:', 'Language:', 'NOTE'))
                        or '-->' in line or line.isdigit()):
                    continue
                raw.append(re.sub(r'<[^>]+>', '', line).strip())
    lines: List[str] = []
    for line in raw:
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return ' '.join(lines)


def write_text_file(subtitle_path: str) -> str:
    txt = os.path.splitext(subtitle_path)[0] + '.txt'
    with open(txt, 'w', encoding='utf-8') as f:
        f.write(to_plain_text(subtitle_path) + '\n')
    return txt


def make_text_postprocessor(ydl):
    """yt-dlp post-processor: after the subtitle file is written, also write <name>.txt."""
    from yt_dlp.postprocessor import PostProcessor

    class TextPostProcessor(PostProcessor):
        def run(self, info):
            for sub in (info.get('requested_subtitles') or {}).values():
                path = sub.get('filepath')
                if path and os.path.exists(path):
                    write_text_file(path)
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


def transcript_path(video_id: str) -> str:
    return os.path.join(TRANSCRIPT_DIR, f'{video_id}.{TRANSCRIPT_FORMAT}')


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
                    subtitlesformat=TRANSCRIPT_FORMAT, outtmpl=os.path.join(TRANSCRIPT_DIR, '%(id)s'))
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.add_post_processor(make_text_postprocessor(ydl), when='before_dl')
            ydl.download([url])
    except Exception as e:
        raise TranscriptError(f'yt-dlp failed: {e}') from e
    # yt-dlp names the files <id>.<lang>.<format> and <id>.<lang>.txt; normalise to <id>.<format> / <id>.txt
    found = sorted(glob.glob(os.path.join(TRANSCRIPT_DIR, f'{video_id}.*.{TRANSCRIPT_FORMAT}')))
    if not found:
        return None
    os.replace(found[0], transcript_path(video_id))
    txts = sorted(glob.glob(os.path.join(TRANSCRIPT_DIR, f'{video_id}.*.txt')))
    if txts:
        os.replace(txts[0], os.path.splitext(transcript_path(video_id))[0] + '.txt')
        for extra in txts[1:]:
            os.remove(extra)
    for extra in found[1:]:
        os.remove(extra)
    return transcript_path(video_id)


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
    from youtube_transcript_api.formatters import SRTFormatter, WebVTTFormatter
    formatter = {'srt': SRTFormatter, 'vtt': WebVTTFormatter}.get(TRANSCRIPT_FORMAT)
    if formatter is None:
        raise TranscriptError(f"youtube_transcript_api supports formats srt and vtt, not {TRANSCRIPT_FORMAT} "
                              f"(use --method ytdlp for it)")
    api = _transcript_api(proxy, ws_user, ws_pass)
    try:
        transcripts = list(api.list(video_id))
        if not transcripts:
            return None
        chosen = next((t for t in transcripts if t.language_code in LANGS), transcripts[0])
        fetched = chosen.fetch()
    except Exception as e:
        raise TranscriptError(f'youtube-transcript-api failed: {e}') from e
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    with open(transcript_path(video_id), 'w', encoding='utf-8') as f:
        f.write(formatter().format_transcript(fetched))
    write_text_file(transcript_path(video_id))
    return transcript_path(video_id)


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
        txt_path = os.path.splitext(path)[0] + '.txt'
        if not os.path.exists(txt_path):
            write_text_file(path)
        text = open(txt_path, encoding='utf-8').read()
        results[method] = (path, txt_path)
        rows.append((method, 'ok', f'{os.path.getsize(path) // 1024} KB {TRANSCRIPT_FORMAT}',
                     f'{len(text.split())} words', f'{len(text)} chars', txt_path))
    print(f'\nCompare for {video_id}')
    for method, status, a, b, c, d in rows:
        print(f'  {method:<24} {status:<7} {a}  {b}  {c}')
        for label, p in zip((TRANSCRIPT_FORMAT, 'txt'), results.get(method, ())):
            print(f'  {"":<24}         {label}: {p}')
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
    p.add_argument('--format', choices=FORMATS, help='subtitle format (or TRANSCRIPT_FORMAT; default srt)')
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

    global TRANSCRIPT_FORMAT
    fmt = args.format or os.getenv('TRANSCRIPT_FORMAT') or TRANSCRIPT_FORMAT
    if fmt not in FORMATS:
        sys.exit(f'Format must be one of {", ".join(FORMATS)} (got {fmt!r})')
    TRANSCRIPT_FORMAT = fmt

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
    logger.info('Method: %s (no fallback)', method)

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
