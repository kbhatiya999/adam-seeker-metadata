# Primer 3: Plugins and entry points

**You need:** basic Python classes. **Read after:** [02-metadata-and-entry-points.md](02-metadata-and-entry-points.md) (what `entry_points.txt` and `METADATA` are and who writes them). **Reference:** the Plugins section of [../architecture.md](../architecture.md).

## The idea in one minute
A plugin is a class that does one job: find the channel's videos, or fetch one transcript. The code
does not contain `if method == "ytdlp": ...`. Instead every package announces its plugins in its own
`pyproject.toml`, and at run time the code asks "which plugins exist in this group?" and loads the one
you picked. Adding a plugin means adding a package. Nothing that exists has to change.

## Entry points, concretely
This is in `sdks/videos/pyproject.toml`:

```toml
[project.entry-points."seeker.video_sources"]
youtube_api = "seeker_sdk_videos.sources.youtube_api:YouTubeApiSource"
ytdlp = "seeker_sdk_videos.sources.ytdlp:YtDlpSource"
```

The left side is the name people choose (`MASTER_LIST_METHOD=ytdlp`). The right side is
`module.path:ClassName`. When uv installs the package it copies these lines into the package's
metadata (a file called `entry_points.txt` inside its `.dist-info` folder), and Python's
`importlib.metadata.entry_points(group=...)` reads them back. Two things follow from that:

- The group is only a string. Names must be unique **inside a group**, so `ytdlp` can be both a video
  source and a transcript method.
- The metadata is written **at install time**. If you add or change an entry point, nothing sees it
  until you run `uv sync --all-packages`. Primer 2 has a small exercise that shows this.

## The two groups

| Group | Base class | Shipped plugins | Chosen by |
|---|---|---|---|
| `seeker.video_sources` | `VideoSource` in `sdks/videos/src/seeker_sdk_videos/sources/base.py` | `youtube_api`, `ytdlp` | `MASTER_LIST_METHOD` |
| `seeker.transcript_methods` | `TranscriptMethod` in `sdks/transcripts/src/seeker_sdk_transcripts/methods/base.py` | `ytdlp`, `youtube_transcript_api` | `--method` or `TRANSCRIPT_METHOD` |

## How the code uses the registry
`sdks/core/src/seeker_sdk_core/plugins.py` is the whole registry (about 50 lines):

- `names(group)` lists the plugin names. `describe(group)` says where each one comes from.
- `load(group, name)` returns the **class**, not an object. The caller builds the object:
  `make_source(...)` for videos (`sdks/videos/src/seeker_sdk_videos/method.py`) and `get_method(...)`
  for transcripts (`sdks/transcripts/src/seeker_sdk_transcripts/service.py`).
- `register(group, name, plugin)` adds a plugin for this process only, and wins over an entry point
  with the same name. Tests and notebooks use it. `unregister` removes it.
- Errors are `PluginError`. "no plugin 'x' in group; available: ..." means the name is wrong.
  "failed to load: ..." means the plugin exists but importing it broke, and the message carries the real
  cause (often a dependency missing from the plugin's own `pyproject.toml`).

## What a plugin has to do
**A video source** sets `name`, `requires_api_key` and `discovery_label`, and implements
`channel_id`, `fetch_recent` and `fetch_all`. The fetch methods return dicts built with
`seeker_sdk_core.new_video(...)`. Look at the `strict` flag: when the user chose the method
explicitly, a failure must be **raised**. Otherwise log it and return an empty result.

**A transcript method** sets `name` and implements `check` and `download`. `download` returns the main
file (srt, else vtt, else txt), or `None` when the video has no captions. Failures raise
`TranscriptError`.

**No fallback, ever.** A chosen method is the only one used. A plugin must not quietly call another
plugin when it fails.

## Write one
```bash
mise run sdk:new -- bing --plugin video_sources
```

That creates `sdks/bing` (`seeker-sdk-bing`, import `seeker_sdk_bing`) with a skeleton class and its
entry point already declared. Then:

1. Fill in the three methods in `sdks/bing/src/seeker_sdk_bing/sources.py`.
2. Run `uv sync --all-packages` so the entry point is installed.
3. Run `uv run seeker plugins` and check that `bing` is listed.
4. Pick it with `MASTER_LIST_METHOD=bing` (see "Method switches" in `AGENTS.md`).
5. Test it without the network (next section).

## Try it (read-only)
```bash
uv run seeker plugins
```

```bash
uv run python -c "from seeker_sdk_core import plugins; print(plugins.describe(plugins.VIDEO_SOURCES))"
```

## Testing a plugin
Register a fake, use it, and always remove it:

```python
plugins.register(plugins.VIDEO_SOURCES, "fake", FakeSource)
try:
    ...  # resolve_method(None, {"MASTER_LIST_METHOD": "fake"}) now works
finally:
    plugins.unregister(plugins.VIDEO_SOURCES, "fake")
```

A working example is in `sdks/videos/tests/test_method_and_service.py`. The registry itself is tested
in `sdks/core/tests/test_plugins.py`, including a check that the shipped plugins are discovered.

## Mistakes we want to avoid
- **"My plugin isn't found."** You changed `pyproject.toml` and did not sync. (The Tilt `plugins`
  resource syncs first for you.)
- **A fake left registered.** It leaks into other tests. Use `try/finally`.
- **Reading the environment or the current folder inside a plugin.** Plugins are built with a config
  object. Take what you need from it, as `SourceConfig` and `TranscriptConfig` do.
- **Adding fallback logic.** If you want "try A then B", that is a decision for the app, made visible
  to the user, not hidden inside an SDK.
