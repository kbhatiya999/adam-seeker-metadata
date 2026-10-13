"""Transcript method: yt-dlp (downloads the caption file, then a yt-dlp post-processor converts it)."""

import glob
import logging
import os
from typing import Any, Dict, Optional, Tuple

import yt_dlp

from seeker_sdk_core import TranscriptError

from ..formats import primary_path, produce_finals, transcript_path
from .base import TranscriptMethod

logger = logging.getLogger(__name__)


def pick_language(info: Dict[str, Any]) -> Optional[Tuple[str, bool]]:
    """Pick ONE caption track: (language, is_automatic).

    Asking yt-dlp for several languages (e.g. 'en.*') makes YouTube answer HTTP 429, and
    machine-translated tracks (such as 'en' on a Hindi video) are rate-limited the hardest.
    So use the video's own language: a manual track (English if there is one), otherwise the
    automatic original ('xx-orig'), otherwise automatic English, otherwise the first one.
    """
    # 'live_chat' is the chat replay of a live stream, not captions
    manual = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat"}
    auto = {k: v for k, v in (info.get("automatic_captions") or {}).items() if k != "live_chat"}
    if manual:
        return ("en" if "en" in manual else next(iter(manual))), False
    if auto:
        orig = next((k for k in auto if k.endswith("-orig")), None)
        if orig:
            return orig, True
        return ("en" if "en" in auto else next(iter(auto))), True
    return None


def _make_text_postprocessor(ydl, finals, keep_source):
    """yt-dlp post-processor: turn each downloaded subtitle file into the FINAL formats.

    Registered at `before_dl`, which runs even with skip_download. yt-dlp's built-in
    FFmpegSubtitlesConvertorPP would need ffmpeg (and cannot write txt).
    """
    from yt_dlp.postprocessor import PostProcessor

    class TextPostProcessor(PostProcessor):
        def run(self, info):
            for sub in (info.get("requested_subtitles") or {}).values():
                path = sub.get("filepath")
                if path and os.path.exists(path):
                    produce_finals(path, os.path.splitext(path)[0], finals, keep_source)
            return [], info

    return TextPostProcessor(ydl)


class YtDlpMethod(TranscriptMethod):
    name = "ytdlp"

    def _base_opts(self) -> Dict[str, Any]:
        net = self.config.network
        if net.cookies_file and not os.path.exists(net.cookies_file):
            raise TranscriptError(f"Cookies file not found: {net.cookies_file}")
        opts: Dict[str, Any] = {"quiet": True, "no_warnings": True, "skip_download": True}
        if net.cookies_file:
            opts["cookiefile"] = net.cookies_file
        if net.proxy:
            opts["proxy"] = net.proxy
        return opts

    def check(self, video_id: str) -> bool:
        try:
            with yt_dlp.YoutubeDL(self._base_opts()) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            return bool(info.get("subtitles") or info.get("automatic_captions"))
        except TranscriptError:
            raise
        except Exception as e:
            raise TranscriptError(f"ytdlp availability check failed: {e}") from e

    def download(self, video_id: str, out_dir: str) -> Optional[str]:
        cfg = self.config
        os.makedirs(out_dir, exist_ok=True)
        url = f"https://www.youtube.com/watch?v={video_id}"
        base = self._base_opts()
        try:
            with yt_dlp.YoutubeDL(base) as ydl:
                info = ydl.extract_info(url, download=False)
            choice = pick_language(info)
            if not choice:
                return None
            lang, is_auto = choice
            logger.info("%s: using %s captions in %s", video_id, "automatic" if is_auto else "manual", lang)
            opts = dict(base, writesubtitles=not is_auto, writeautomaticsub=is_auto, subtitleslangs=[lang],
                        subtitlesformat=cfg.source_format, outtmpl=os.path.join(out_dir, "%(id)s"))
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.add_post_processor(_make_text_postprocessor(ydl, cfg.finals, cfg.keep_source), when="before_dl")
                ydl.download([url])
        except Exception as e:
            raise TranscriptError(f"yt-dlp failed: {e}") from e
        # yt-dlp names files <id>.<lang>.<ext>; normalise every file we keep to <id>.<ext>
        kept = list(cfg.finals) + ([cfg.source_format] if cfg.keep_source else [])
        got_any = False
        for ext in dict.fromkeys(kept):
            found = sorted(glob.glob(os.path.join(out_dir, f"{video_id}.*.{ext}")))
            if not found:
                continue
            got_any = True
            os.replace(found[0], transcript_path(out_dir, video_id, ext))
            for extra in found[1:]:
                os.remove(extra)
        return primary_path(out_dir, video_id, cfg.finals) if got_any else None
