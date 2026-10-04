#!/usr/bin/env python3
"""
Transcript downloading for videos in the master list.

The method is chosen explicitly (--method or TRANSCRIPT_METHOD) and there is NO fallback:
if the chosen method fails, the failure is reported and nothing else is tried.

  ytdlp                   yt-dlp (optional cookies file, optional proxy URL)
  youtube_transcript_api  youtube-transcript-api (optional Webshare or generic proxy)

Transcripts are saved as data/transcripts/<video_id>.vtt and linked from the master list
(transcript_file, transcript_downloaded, transcript_download_date).

Optional environment (declared in fnox.toml):
  TRANSCRIPT_METHOD, YTDLP_COOKIES_FILE, PROXY_URL,
  WEBSHARE_PROXY_USERNAME, WEBSHARE_PROXY_PASSWORD
"""

import argparse
import glob
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

METHODS = ('ytdlp', 'youtube_transcript_api')
TRANSCRIPT_DIR = 'data/transcripts'
LANGS = ['en']

logger = logging.getLogger('transcripts')


class TranscriptError(Exception):
    """Raised when the chosen method cannot produce a transcript."""


def transcript_path(video_id: str) -> str:
    return os.path.join(TRANSCRIPT_DIR, f'{video_id}.vtt')


def download_ytdlp(video_id: str, cookies_file: Optional[str], proxy: Optional[str]) -> Optional[str]:
    import yt_dlp
    if cookies_file and not os.path.exists(cookies_file):
        raise TranscriptError(f'Cookies file not found: {cookies_file}')
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    opts = {
        'quiet': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en.*', 'en'],
        'subtitlesformat': 'vtt',
        'outtmpl': os.path.join(TRANSCRIPT_DIR, '%(id)s'),
    }
    if cookies_file:
        opts['cookiefile'] = cookies_file
    if proxy:
        opts['proxy'] = proxy
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
    except Exception as e:
        raise TranscriptError(f'yt-dlp failed: {e}') from e
    # yt-dlp names files <id>.<lang>.vtt; normalise to <id>.vtt
    found = sorted(glob.glob(os.path.join(TRANSCRIPT_DIR, f'{video_id}.*.vtt')))
    if not found:
        return None
    os.replace(found[0], transcript_path(video_id))
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
    from youtube_transcript_api.formatters import WebVTTFormatter
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
        f.write(WebVTTFormatter().format_transcript(fetched))
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
                v['transcript_downloaded'] = True
                v['transcript_download_date'] = datetime.now().isoformat()[:10]
                return
        raise TranscriptError(f'Video {video_id} not in master list')


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
    args = p.parse_args()

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
        master.link(vid, path)
        master.save()
        logger.info('%s: saved %s', vid, path)
        ok += 1
    print(f'Done: {ok} downloaded, {failed} failed/unavailable')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
