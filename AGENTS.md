# AGENTS.md

Metadata repo for the YouTube channel https://www.youtube.com/@AdamSeekerOfficial. A daily GitHub Action discovers new videos and commits them to `data/videos_master.json`.

## Layout
- `data/videos_master.json` — master list (`videos`, `last_updated`, `total_videos`, `channel_url`). Auto-updated; also holds `.backup` copies.
- `scripts/update_master.py` — daily update; `--rebuild` does a full rebuild. Needs `YOUTUBE_API_KEY`.
- `scripts/rebuild_master.py` — full rebuild from scratch.
- `scripts/transcripts.py` — transcript download/management (`stats`, `list-missing`, `download-missing`, `download`, `check`). Method is explicit (`--method` or `TRANSCRIPT_METHOD`: `ytdlp` or `youtube_transcript_api`), no default and NO fallback. Saves `data/transcripts/<id>.vtt` (git-ignored; transcripts are large) and links `transcript_file`/`transcript_downloaded`/`transcript_download_date` in the master list. Optional proxy/cookies via `PROXY_URL`, `WEBSHARE_PROXY_USERNAME/PASSWORD`, `YTDLP_COOKIES_FILE` (declared in `fnox.toml`).
- `scripts/manage_videos.py` — manual categorizing/scoring (`list-uncategorized`, `categorize`, `priority`, `report`, `interactive`).
- `.github/workflows/update-videos.yml` — daily at 06:00 UTC (also manual and on script/data pushes).
- `.github/workflows/rebuild-videos.yml` — manual rebuild.
- `logs/` — script logs, committed by the workflow.
- Docs: `README.md` (yt-dlp transcripts), `README_AUTOMATION.md`, `README_REBUILD.md`.

## Conventions
- Keep `videos` sorted by `upload_date`, newest first. Both save paths sort; if you add a new write path, sort there too.
- New videos start with `status: "uncategorized"`, `auto_detected: true`, `needs_review: true`.
- The update workflow keeps ONE open issue titled "📺 New Videos Available for Review" (labels `automation`, `videos`, `review-needed`) and comments on it; closing it makes the next run open a new one. Don't reintroduce one issue per run.
- Never commit a real API key; `config.env` holds placeholders only. The key comes from the `YOUTUBE_API_KEY` secret.
- `data/videos_master.json` is written with `indent=2, ensure_ascii=False`; keep that format to avoid noisy diffs.
- Update the READMEs when workflow behavior changes.

## Setup and tasks (mise + uv)
Tools and tasks are defined in `mise.toml`; dependencies in `pyproject.toml` / `uv.lock` (no requirements.txt).
- `mise install` then `mise run install` — installs the tools (Python 3.12, uv, act, fnox, gh, gcloud), syncs `.venv` (`setup`), and runs `scripts/check_docker.sh`, which checks Docker (needed only for `act:` tasks) and offers to install it with Homebrew on macOS if missing.
- Secrets use fnox: declared in `fnox.toml`; put `YOUTUBE_API_KEY` in the git-ignored `fnox.local.toml` (copy `fnox.local.toml.example`), which overrides `fnox.toml`. Tasks run via `fnox exec`; in CI the key comes from the environment. Never commit `fnox.local.toml`.
- Task names are `<where>:<area>:<action>`. The first scope says where it runs:
  - `local:` runs the code directly: `local:videos:update` / `local:videos:rebuild` / `local:videos:manage <subcommand>`, `local:transcripts:manage -- <args>` (e.g. `-- --method youtube_transcript_api download-missing --limit 5`).
  - `act:` runs the workflow locally in Docker: `act:videos:update` / `act:videos:rebuild` / `act:list`. Commit, push, issue and artifact steps are skipped when `ACT` is set, so it never publishes anything.
  - `gh:` triggers the REAL workflow on GitHub and watches it: `gh:videos:update` / `gh:videos:rebuild` / `gh:list`. It really commits and creates issues. Uses the current branch (or `REF=...`); the ref must be pushed and the workflow must exist on the default branch.
  - `install` (full first-time setup), `setup` (just `uv sync`) and `nuke` (cleanup) are unscoped (repo-wide).
- `mise run nuke` is the opposite of `install`: removes `.venv`, `.act/` and this project's Docker containers (label `project=adam-seeker-metadata`), their volumes, and the act runner image. Flags after `--`: `--dry-run`, `--yes`, `--all` (also uv cache, `act-toolcache` volume, this project's mise tool versions, `fnox.local.toml`). Everything act creates is predictable (see `.actrc`: label, `.act/` dirs, pinned image) so nuke can find it. Docker itself is never uninstalled. If you add new Docker/act artifacts, keep them labelled/under `.act/` and update `scripts/nuke.sh`.
- `mise run local:apikey:setup` (`scripts/api_key.sh`): guided YouTube Data API v3 key setup. gcloud is a mise tool (its installer needs Python 3.10+, hence `CLOUDSDK_PYTHON` in `mise.toml` and `scripts/ensure_gcloud.sh`). A key can only be created from the user's own Google account, so it can't be fetched automatically: it can drive gcloud after the user signs in (enable API, create a restricted key), or it opens the console pages, validates the pasted key with one API call (key sent via header, never printed), saves it to git-ignored `fnox.local.toml` (mode 600) and optionally sets the `YOUTUBE_API_KEY` GitHub secret.
- Docker lifecycle (`scripts/docker.sh`, runtime detection: Colima first, then Docker Desktop on macOS): `docker:start` starts it and waits until ready; `docker:stop` removes this project's containers/volumes then stops Colima / quits Docker Desktop (skipped if other containers are running); `docker:cleanup` removes only our leftovers; `docker:diagnose` (read-only, `scripts/docker_diagnose.sh`) compares host CPU/RAM/disk with what Docker is allocated, shows Docker disk usage, live container usage and free space in the VM, gives a verdict against act's needs (2+ CPU, 4+ GB RAM, 30+ GB disk) and prints how to change the allocation persistently for the detected runtime (Colima: `colima start --edit` / `~/.colima/default/colima.yaml`; Docker Desktop: Settings > Resources). `act:` tasks run through `docker.sh run`: they clean old leftovers first (replace, never reuse), start Docker only if it was down, always clean up afterwards (also on failure/Ctrl-C) and stop Docker only if that run started it, so nothing is orphaned.
- Workflows call the `local:` tasks, so local, act and GitHub run the same commands. Test order: `local:` then `act:` then `gh:`.
- After changing dependencies run `uv lock` and commit `uv.lock`.
