# Primer 2: How an installed package describes itself (METADATA and entry_points.txt)

**You need:** nothing. **Read before:** [03-plugins-and-entry-points.md](03-plugins-and-entry-points.md), which depends on this.

## The short version
- Your code (`.py` files) does not say what the package is called, what it needs, or which plugins it
  offers. That information is written in a small folder next to the code, called **`.dist-info`**.
- Inside that folder, **`METADATA`** is the package's **label** (name, version, what it needs).
- **`entry_points.txt`** is the package's **menu**: "these are the plugins and commands I offer".
- **uv writes both files when it installs the package**, copying them from your `pyproject.toml`.
  Python reads them later. Nothing updates them when you edit `pyproject.toml`. That is why you run
  `uv sync` after changing it.

## A picture to hold on to
Think of a package as a product on a shelf. The product itself is the code. The **label on the box**
(`METADATA`) says what it is and what else you need to use it. A **menu card on the box**
(`entry_points.txt`) says what it can do for others. Labels are printed when the product is boxed
(installed), so changing the recipe (`pyproject.toml`) does not change the printed label until you box it
again (`uv sync`).

## Where the folder is
Every installed package has one, next to its code, in the environment's `site-packages`. For this repo:

```
.venv/lib/python3.12/site-packages/seeker_sdk_videos-0.1.0.dist-info/
```

`.venv` is created by `mise run setup` and is git-ignored. Never edit files in it by hand: the next
`uv sync` rewrites them.

What is inside (you only need to care about the first two):

| File | What it is |
|---|---|
| **`METADATA`** | the label: name, version, requirements |
| **`entry_points.txt`** | the menu: plugins and commands the package offers |
| `RECORD` | list of the files the install created, with a hash and size for each. Used to uninstall cleanly. |
| `WHEEL`, `INSTALLER`, `REQUESTED`, `direct_url.json`, `uv_*.json` | bookkeeping about how and by whom it was installed |

## METADATA, line by line
Left: what you write in `sdks/videos/pyproject.toml`. Right: what ends up in the installed `METADATA`.

| In `pyproject.toml` | In `METADATA` |
|---|---|
| `name = "seeker-sdk-videos"` | `Name: seeker-sdk-videos` |
| `version = "0.1.0"` | `Version: 0.1.0` |
| `description = "..."` | `Summary: ...` |
| `requires-python = ">=3.11"` | `Requires-Python: >=3.11` |
| `dependencies = ["seeker-sdk-core>=0.1.0", "requests>=2.31.0", ...]` | one `Requires-Dist:` line per dependency |
| `readme = "README.md"` | the README text, pasted below the headers |

Python reads it for you:

```python
from importlib.metadata import version, requires
version("seeker-sdk-videos")    # '0.1.0'
requires("seeker-sdk-videos")   # ['seeker-sdk-core>=0.1.0', 'requests>=2.31.0', 'yt-dlp>=2023.12.30']
```

`pip list`, `uv pip list` and `uv pip check` read the same file.

## entry_points.txt, line by line
It is a tiny text file. Each **section** is a group name, and each line is `name = where to find it`:

```
[seeker.video_sources]
youtube_api = seeker_sdk_videos.sources.youtube_api:YouTubeApiSource
ytdlp = seeker_sdk_videos.sources.ytdlp:YtDlpSource
```

It comes from this part of `pyproject.toml`:

```toml
[project.entry-points."seeker.video_sources"]
youtube_api = "seeker_sdk_videos.sources.youtube_api:YouTubeApiSource"
ytdlp = "seeker_sdk_videos.sources.ytdlp:YtDlpSource"
```

### The three parts of a line
`ytdlp = seeker_sdk_videos.sources.ytdlp:YtDlpSource`

1. **`ytdlp`** is the **name** a person chooses (`MASTER_LIST_METHOD=ytdlp`).
2. **`seeker_sdk_videos.sources.ytdlp`** is the **module**: the file `ytdlp.py` inside
   `seeker_sdk_videos/sources/`.
3. **`YtDlpSource`** is the **thing inside that module**, here a class.

Loading it means exactly: `import seeker_sdk_videos.sources.ytdlp`, then take `YtDlpSource` from it.
That is all `EntryPoint.load()` does. It gives you the class, not an object made from it.

### Two kinds of sections
- **Our own groups**, like `seeker.video_sources` and `seeker.transcript_methods`. Nothing in Python
  knows about these. We invented the names, and our `plugins.py` asks for them.
- **`console_scripts`**, a group Python tools know. It comes from `[project.scripts]` and is how the
  `seeker` command exists. In `apps/cli`:

  ```
  [console_scripts]
  seeker = seeker_cli.main:main
  ```

  At install time uv turns that line into the little program `.venv/bin/seeker`, which just does
  `from seeker_cli.main import main` and runs it.

### Reading it
```python
from importlib.metadata import entry_points
for ep in entry_points(group="seeker.video_sources"):
    print(ep.name, ep.value, ep.dist.name)   # ytdlp  seeker_sdk_videos.sources.ytdlp:YtDlpSource  seeker-sdk-videos
cls = ep.load()                               # the class YtDlpSource
```

Nothing is imported until you call `.load()`. Listing the plugins is cheap and cannot break because a
plugin's code has a bug or a missing dependency.

## The whole journey
```
you edit pyproject.toml            <- the only file you edit
      |
uv lock                            writes uv.lock (the solved list of exact versions)
      |
uv sync --all-packages             installs. For each workspace package uv writes the .dist-info folder:
      |                            METADATA, entry_points.txt, RECORD, ... and a .pth file that points
      |                            Python at the package's src/ folder
      v
Python's importlib.metadata        reads those files when asked (version(), entry_points(group=...))
      |
sdks/core/.../plugins.py           our code: names(), load(), describe()
      |
make_source() / get_method()       build an object from the class and use it
```

| Step | Who does it | Where the code is |
|---|---|---|
| Copy `pyproject.toml` into METADATA and entry_points.txt | uv, with its built-in `uv_build` backend (`WHEEL` says `Generator: uv ...`) | inside the uv program, not in this repo |
| Read the files, `ep.load()` | Python standard library | `importlib/metadata/__init__.py` |
| Ask for a group, wrap errors in `PluginError` | our code | `sdks/core/src/seeker_sdk_core/plugins.py` |

## Try it 1: look at the real files (read-only)
```bash
cat .venv/lib/python3.12/site-packages/seeker_sdk_videos-0.1.0.dist-info/METADATA
```

```bash
cat .venv/lib/python3.12/site-packages/seeker_sdk_videos-0.1.0.dist-info/entry_points.txt
```

```bash
cat .venv/lib/python3.12/site-packages/seeker_cli-0.1.0.dist-info/entry_points.txt .venv/bin/seeker
```

## Try it 2: see that the label does not update by itself
This builds a tiny throwaway package in a temporary folder (nothing in the repo is touched, and the
brackets keep your own terminal in its current folder), edits its `pyproject.toml`, and shows what
Python sees before and after reinstalling.

```bash
(
set -e
demo="$(mktemp -d)" && cd "$demo" && mkdir -p src/demo_pkg
cat > pyproject.toml <<'EOF'
[project]
name = "demo-pkg"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = []

[project.entry-points."demo.plugins"]
first = "demo_pkg:First"

[build-system]
requires = ["uv_build>=0.11,<0.12"]
build-backend = "uv_build"
EOF
printf 'class First: ...\nclass Second: ...\n' > src/demo_pkg/__init__.py
uv venv -q .venv && uv pip install -q --python .venv/bin/python -e .
show() { .venv/bin/python -c "
from importlib.metadata import entry_points, version
print('  version', version('demo-pkg'), '| plugins', sorted(e.name for e in entry_points(group='demo.plugins')))"; }
echo "installed:"; show
sed -i.bak 's/version = "1.0.0"/version = "2.0.0"/; s#first = "demo_pkg:First"#first = "demo_pkg:First"\nsecond = "demo_pkg:Second"#' pyproject.toml
echo "pyproject.toml edited, not reinstalled:"; show
uv pip install -q --python .venv/bin/python -e .
echo "reinstalled:"; show
)
```

You should see version `1.0.0` and only `first` twice, then `2.0.0` and `first, second` after the
reinstall. The edit to the file changed nothing until the install rewrote the `.dist-info`.

## Mistakes we have made or can easily make
- **"My new plugin is not found."** You edited `pyproject.toml` and did not run `uv sync --all-packages`.
  Try it 2 shows why. (The Tilt `plugins` resource syncs first for this reason.)
- **A version bump seems ignored.** `importlib.metadata.version(...)` reads the installed `METADATA`, so it
  keeps the old number until the next sync.
- **Editing files inside `.venv`.** They are generated. Change `pyproject.toml` and sync instead.
- **A plugin that is listed but fails to load.** Listing reads only the text file. `.load()` imports the
  code, so a missing dependency or a typo in the `module:Class` path shows up there, as a `PluginError`
  from `plugins.py`.
- **Two packages offering the same name in one group.** Python finds both, `names()` shows the name only
  once, and `load` returns the first one it finds. Keep names unique inside a group.
- **Mixing up the three names.** The distribution name (`seeker-sdk-videos`, in METADATA), the import name
  (`seeker_sdk_videos`, the folder you `import`) and the plugin name (`ytdlp`, in `entry_points.txt`) are
  different things.

## Words used here
- **Distribution:** an installable package, named in `pyproject.toml` (`seeker-sdk-videos`).
- **`.dist-info`:** the folder of facts about one installed distribution.
- **Editable install:** the code stays in your repo (`sdks/videos/src`) and a `.pth` file points Python
  there, so code edits show up at once. The `.dist-info` is still a copy.
- **Entry point:** one `name = module:thing` line in `entry_points.txt`.
- **Group:** the section name in `entry_points.txt` that entry points are filed under.
