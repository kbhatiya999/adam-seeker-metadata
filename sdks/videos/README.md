# seeker-sdk-videos

Finds the videos of a YouTube channel and keeps the master list (`seeker-sdk-core`) current.

- **Sources are plugins** (entry-point group `seeker.video_sources`): `youtube_api` (needs an API
  key) and `ytdlp` (flat listing, works from cloud IPs). Add a source in another package by
  declaring an entry point; nothing here changes.
- **Explicit method, no fallback** (`MASTER_LIST_METHOD`): a chosen source is used and any failure
  is an error. Unset keeps the old implicit behaviour (API if a key exists, else yt-dlp).
- `update()` adds new videos; `rebuild()` replaces the list from YouTube and keeps manual work.
- `catalog`: categorize videos, priorities, report data.

```python
from seeker_sdk_videos import make_source, resolve_method, update

choice = resolve_method(api_key=None)            # -> MethodChoice(name="ytdlp", explicit=False)
source = make_source(choice, api_key=None)
result = update("data/videos_master.json", "https://www.youtube.com/@AdamSeekerOfficial", source)
print(len(result.new_videos), "new videos")
```
