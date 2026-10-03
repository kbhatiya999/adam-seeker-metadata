# AGENTS.md

Metadata repo for the YouTube channel https://www.youtube.com/@AdamSeekerOfficial. A daily GitHub Action discovers new videos and commits them to `data/videos_master.json`.

## Layout
- `data/videos_master.json` — master list (`videos`, `last_updated`, `total_videos`, `channel_url`). Auto-updated; also holds `.backup` copies.
- `scripts/update_master.py` — daily update; `--rebuild` does a full rebuild. Needs `YOUTUBE_API_KEY`.
- `scripts/rebuild_master.py` — full rebuild from scratch.
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
- `mise install` then `mise run setup` — install Python 3.12, uv, act and sync `.venv`.
- Put `YOUTUBE_API_KEY` in `.env` (git-ignored; see `.env.example`).
- `mise run update` / `rebuild` / `manage <subcommand>` — run the scripts.
- `mise run ci:update` / `ci:rebuild` — run the GitHub workflows locally with `act` (needs Docker running). Commit, push, issue and artifact steps are skipped when `ACT` is set, so a local run never publishes anything. Workflows call `mise run ...`, so local and CI run the same commands.
- After changing dependencies run `uv lock` and commit `uv.lock`.
