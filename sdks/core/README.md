# seeker-sdk-core

Shared foundation of the Seeker SDKs. No third-party dependencies.

- `MasterList`: load / sort / merge / save the master video list JSON (`data/videos_master.json`),
  with the same file format and backup behaviour the scripts always had.
- Plugin registry (`seeker_sdk_core.plugins`): discovers plugins through Python entry points, so a
  new SDK can add a video source or a transcript method without changing any existing package.
- Settings helpers, errors and logging setup.

```python
from seeker_sdk_core import MasterList

master = MasterList.load("data/videos_master.json")
print(len(master.videos), "videos")
```

Extension points (entry-point groups): `seeker.video_sources`, `seeker.transcript_methods`.
