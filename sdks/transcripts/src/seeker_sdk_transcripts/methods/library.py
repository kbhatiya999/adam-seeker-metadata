"""Transcript method: youtube-transcript-api, downloading the same source format as yt-dlp.

The library normally returns parsed snippets only. Each Transcript object knows its timedtext URL
and the configured (proxy-aware) HTTP session, so we request that URL with &fmt=<format>
(YouTube serves ttml, srv1, srt and vtt) and keep the raw file, like yt-dlp does. This relies on
the library's private `_url` / `_http_client` (checked below; revisit when upgrading the library).
"""

import os
from typing import Optional

from seeker_sdk_core import TranscriptError

from ..formats import primary_path, produce_finals, transcript_path
from .base import TranscriptMethod


class TranscriptApiMethod(TranscriptMethod):
    name = "youtube_transcript_api"

    def _api(self):
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig
        net = self.config.network
        if net.webshare_username and net.webshare_password:
            return YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(
                proxy_username=net.webshare_username, proxy_password=net.webshare_password))
        if net.proxy:
            return YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=net.proxy, https_url=net.proxy))
        return YouTubeTranscriptApi()

    def check(self, video_id: str) -> bool:
        try:
            return any(True for _ in self._api().list(video_id))
        except Exception as e:
            raise TranscriptError(f"youtube_transcript_api availability check failed: {e}") from e

    def download(self, video_id: str, out_dir: str) -> Optional[str]:
        cfg = self.config
        try:
            transcripts = list(self._api().list(video_id))
            if not transcripts:
                return None
            chosen = next((t for t in transcripts if t.language_code in cfg.languages), transcripts[0])
            if not (hasattr(chosen, "_url") and hasattr(chosen, "_http_client")):
                raise TranscriptError("youtube-transcript-api changed its internals; update seeker-sdk-transcripts")
            if "&exp=xpe" in chosen._url:
                raise TranscriptError("YouTube requires a PO token for this video (not supported)")
            response = chosen._http_client.get(f"{chosen._url}&fmt={cfg.source_format}")
            response.raise_for_status()
        except TranscriptError:
            raise
        except Exception as e:
            raise TranscriptError(f"youtube-transcript-api failed: {e}") from e
        os.makedirs(out_dir, exist_ok=True)
        source = transcript_path(out_dir, video_id, f"source.{cfg.source_format}")
        with open(source, "wb") as f:
            f.write(response.content)
        produce_finals(source, os.path.join(out_dir, video_id), cfg.finals, cfg.keep_source)
        return primary_path(out_dir, video_id, cfg.finals)
