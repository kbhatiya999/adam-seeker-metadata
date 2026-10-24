# Automation reference

Every task in detail. **New here? Start with [README.md](README.md):** it covers installing, the first commands and setting up GitHub.

All commands run through mise: `mise run <task>`. The task names follow one pattern, `<where>:<area>:<action>`, for example `local:videos:update`. `mise tasks` lists them all.

## What is where

```
data/videos_master.json        the video list (committed; GitHub updates it daily)
data/videos_master.json.backup the copy made before every save
data/transcripts/              downloaded transcripts (git-ignored: large)
data/knowledge/ data/llm/ data/eval/   processed passages, model answers, evaluation runs (git-ignored)
logs/                          update_master.log, rebuild_master.log (committed by the workflow), transcripts.log
sdks/                          the libraries: core, videos, transcripts, llm, gemini, knowledge, chat, eval
apps/                          the front ends: cli (`seeker`), tui (the menu), chat (Chainlit)
scripts/                       helper scripts behind the mise tasks (keys, Docker, profiles, nuke, builds)
eval/questions/                the evaluation questions
.github/workflows/             update-videos.yml (daily), rebuild-videos.yml (manual)
mise.toml                      the tools and every task
fnox.toml                      the names of all secrets and settings, and the profiles (no values)
fnox.local.toml                YOUR keys and settings (git-ignored; copy fnox.local.toml.example)
pyproject.toml, uv.lock        the Python workspace and its exact dependency versions
Tiltfile                       the dashboard
```

## Where a task runs: `local:`, `act:`, `gh:`

| Scope | Runs | Publishes? |
|---|---|---|
| `local:` | the code directly on your computer | no, but it edits `data/` and `logs/` in your folder |
| `act:` | the GitHub workflow in Docker, using `act` | no: commit, push, issue and artifact steps are skipped when `ACT` is set |
| `gh:` | the real workflow on GitHub (`gh workflow run`, then it watches the run) | **yes**: commits to the branch and opens or comments on issues |

The workflows call the `local:` tasks, so all three run the same commands. Test in this order: `local:` first, then `act:`, then `gh:`.

`gh:` tasks use your current branch, or `REF=<branch>`. The branch must be pushed. The workflow file must also exist on the default branch, or GitHub cannot start it.

Some tasks have no scope:
- `install`, `setup`, `test`, `menu`, `nuke`
- `build:sdks`, `build:apps`, `sdk:new`

## Videos

```bash
mise run local:videos:update
```
Adds new videos to the list:
- New videos get `status: "uncategorized"` and `needs_review: true`.
- The list stays sorted newest first.
- A `.backup` copy is made before every save.

```bash
mise run local:videos:rebuild
```
Fetches the whole list again and keeps your manual work. See [README_REBUILD.md](README_REBUILD.md).

`local:videos:manage` takes a subcommand: `report`, `list-uncategorized`, `interactive`, `categorize` or `priority`.

```bash
mise run local:videos:manage report
```
Shows counts, categories and the newest videos.

```bash
mise run local:videos:manage list-uncategorized
```
Lists the videos you have not categorized yet.

```bash
mise run local:videos:manage interactive
```
Goes through the new videos one by one.

```bash
mise run local:videos:manage categorize VIDEO_ID --categories "islam,critique" --relevance 8 --notes "Important debate"
```
Categorizes one video. Relevance is a score from 1 to 10.

```bash
mise run local:videos:manage priority VIDEO_ID --category urgent --relevance 10
```
Marks a video as important.

### One video in the list

```json
{
  "video_id": "abc123",
  "title": "Video title",
  "url": "https://www.youtube.com/watch?v=abc123",
  "upload_date": "2026-10-17",
  "description": "...",
  "status": "uncategorized",
  "auto_detected": true,
  "needs_review": true,
  "last_checked": "2026-10-18",
  "categories": ["critique-of-islam"],
  "relevance_score": 9,
  "notes": "Why this video matters",
  "key_topics": ["topic1"],
  "transcript_file": "data/transcripts/abc123.srt",
  "transcript_text_file": "data/transcripts/abc123.txt",
  "transcript_status": "unavailable",
  "transcript_attempts": 2,
  "transcript_retry_after": "2026-10-20"
}
```

Field groups:
- `categories`, `relevance_score`, `notes` and `key_topics` exist only after you add them.
- The `transcript_*` fields are written by the transcript tools.
- `transcript_status` and the fields after it appear only while a video has no transcript yet.

The top of the file has `last_updated`, `total_videos` and `channel_url`. The file is written with 2-space indents and real (not escaped) Unicode, which keeps diffs small.

## Methods: how videos and transcripts are fetched

| Setting | Values | Meaning |
|---|---|---|
| `master-list` (`MASTER_LIST_METHOD`) | `youtube_api`, `ytdlp` | how new videos are found |
| `transcript` (`TRANSCRIPT_METHOD`) | `ytdlp`, `youtube_transcript_api` | how transcripts are downloaded |

- **An explicit method has no fallback.** If it fails, the run fails, and `youtube_api` without a key fails too.
- **With `master-list` unset, the old behaviour applies.** The tools use the API if a key is present, and yt-dlp otherwise.
- **Each place keeps its own copy of the setting:**

```bash
mise run local:method:set -- master-list ytdlp
```
For `local:` tasks. This writes the `overrides` profile in `fnox.local.toml`.

```bash
mise run act:method:set -- master-list youtube_api
```
For `act:` tasks. This writes `.vars`, which is git-ignored.

```bash
mise run gh:method:set -- master-list youtube_api
```
For the real workflows. This sets a repository variable.

```bash
mise run gh:method:set -- master-list unset
```
Removes a setting.

```bash
mise run all:method:show
```
Shows what local, act and GitHub each use. For one place only, use `local:method:show`, `act:method:show` or `gh:method:show`.

The fastest way to switch both methods at once on your computer is a profile:

```bash
mise run local:profile:use -- ytdlp
```

## fnox profiles

[fnox](https://github.com/jdx/fnox) gives every task its keys and settings.

| Where | What goes there |
|---|---|
| top of `fnox.local.toml` | your **keys** (`YOUTUBE_API_KEY`, `GEMINI_API_KEY`). Every profile inherits them. |
| profiles in `fnox.toml` | **settings** only, shared by everyone |
| the `overrides` profile in `fnox.local.toml` | your own settings, applied last. `local:method:set` writes it. |

The profiles:

| Profile | Kind | Sets |
|---|---|---|
| `ytdlp` | methods | both methods to yt-dlp |
| `youtube-api` | methods | `youtube_api` and `youtube_transcript_api` |
| `subagents` | model | model questions wait in a queue (`data/llm/queue/`) for a helper to answer |
| `gemini` | model | Gemini, model `gemini-flash-latest` |
| `gemini-lite` | model | Gemini, model `gemini-flash-lite-latest` (a separate free quota) |
| `proxy` | network | Only in your `fnox.local.toml`, made by `mise run local:proxy:setup`. Transcript requests go through your Webshare proxy. |
| `cookies` | network | Only in your `fnox.local.toml`, made by `mise run local:cookies:setup`. yt-dlp signs in with your YouTube cookies. |

```bash
mise run local:profile:show
```
Shows the active profiles, the settings that result and whether each key is set. Key values are never shown.

```bash
mise run local:profile:use -- ytdlp gemini-lite
```
Picks one methods profile and one model profile. When two profiles set the same thing, the later one wins.

```bash
mise run local:profile:use
```
Goes back to the default.

You can also switch from the menu (Methods → Switch fnox profile) or with the Tilt `profile` resource's "Switch fnox profile" button.

- The choice is saved in `.fnox-profile`, which is git-ignored.
- `FNOX_PROFILE=ytdlp mise run ...` overrides it for one command.
- On GitHub there is no profile, so the default applies and the key comes from the repository secret.

**Never put a setting at the top of `fnox.local.toml`.** A setting there silently beats every profile. Put your own settings in `[profiles.overrides.secrets]` instead (see `fnox.local.toml.example`).

## Keys

```bash
mise run local:apikey:setup
```
Sets up the YouTube Data API v3 key:
- It can drive `gcloud` after you sign in, or open the Google Cloud pages for you.
- It checks the key with one call, saves it in `fnox.local.toml` and can also set the `YOUTUBE_API_KEY` GitHub secret.
- The key is free, and you can only create it from your own Google account.

```bash
mise run local:apikey:gemini
```
Sets up the Gemini key:
- It opens https://aistudio.google.com/apikey, checks the key with a free call and saves it in `fnox.local.toml`.
- `mise run local:apikey:gemini -- --check` checks the saved key again.

```bash
mise run local:proxy:setup
```
Sets up a Webshare proxy, for transcripts where YouTube blocks your address. It blocks GitHub's runners: "Sign in to confirm you're not a bot", tested 2026-10-18.
1. It opens the Webshare dashboard. On the Proxy List page, pick **Username/Password** and **Rotating Proxy Endpoint**.
2. It asks for the proxy username and password, with the password hidden. If `WEBSHARE_PROXY_USERNAME` and `WEBSHARE_PROXY_PASSWORD` are already set in your shell, it asks nothing and uses them.
3. It checks that the proxy accepts them, then asks YouTube about one video through it, with both methods.
4. It saves them as the local `proxy` profile. Your own runs still go direct unless you pick it.

To give it the login through the environment, without typing at a prompt (the password stays out of the command line and out of your shell history):
```bash
export WEBSHARE_PROXY_USERNAME=your-proxy-username
read -rs WEBSHARE_PROXY_PASSWORD && export WEBSHARE_PROXY_PASSWORD
mise run local:proxy:setup
```
Type or paste the password after the second line (nothing is shown), then press Enter. The variables live only in that terminal window.

To type the login into the file yourself, open `fnox.local.toml` (in the repository folder, never committed) and add this at the end, with your own values (the username without `-rotate`):
```toml
[profiles.proxy.secrets]
WEBSHARE_PROXY_USERNAME = { default = "your_proxy_username" }
WEBSHARE_PROXY_PASSWORD = { default = "your_proxy_password" }
```
Then run `mise run local:proxy:setup -- --check`. It tests the proxy and YouTube, and adds or refreshes the `PROXY_URL` line itself, so it is also what to run after you change the password. The same block, commented out, is in `fnox.local.toml.example`.

To use the proxy:
- For one run: `FNOX_PROFILE=proxy mise run local:transcripts:manage -- --method ytdlp download-missing --limit 5`.
- To keep it on: `mise run local:profile:use -- ytdlp proxy`.

Two more forms:
- `mise run local:proxy:setup -- --check` tests the saved proxy again.
- `mise run local:proxy:setup -- --github` copies it to the repository secrets `WEBSHARE_PROXY_USERNAME`, `WEBSHARE_PROXY_PASSWORD` and `PROXY_URL`.

```bash
mise run local:cookies:setup
```
Collects YouTube login cookies for yt-dlp, another way past the "Sign in to confirm you're not a bot" check. Only yt-dlp uses cookies; youtube-transcript-api has no cookie option.

Use a **throwaway Google account**, never your own: yt-dlp's authors warn that accounts used this way can be flagged or banned. Cookies are a saved login, so keep them private.
1. Sign in to YouTube with that account in its own browser profile (a private window works too).
2. Run the task. It asks where the cookies are: **a browser on this computer** (it reads them with yt-dlp, and on macOS may ask to allow the browser's Keychain item: choose Allow), or **a `cookies.txt` you exported** with a browser extension such as "Get cookies.txt LOCALLY".
3. It keeps only the `youtube.com` and `google.com` cookies. Nothing else from your browser is kept.
4. It checks that you are signed in and when the login expires (cookie names only, never values).
5. It saves them as **one base64 line** in the environment variable `YTDLP_COOKIES_BASE64`, in the local `cookies` profile of `fnox.local.toml` (git-ignored, mode 600). There is no cookie file to look after.
6. It asks YouTube about one video with the cookies. From your own computer YouTube answers with or without cookies, so the real test is through the proxy: with a saved `proxy` profile it tries 4 times through the proxy with the cookies and tells you how many got through.
7. It offers to copy the value to the GitHub repository secret of the same name (`-- --github` does it later).

Without questions: `mise run local:cookies:setup -- --browser chrome --profile "Profile 2"` or `-- --file ~/Downloads/cookies.txt`. `-- --check` tests the saved cookies again.

**The same variable everywhere.** The proxy and the cookies are environment variables with the same names in all three places, so nothing is different between them:

| Variable | Local | act | GitHub |
|---|---|---|---|
| `PROXY_URL`, `WEBSHARE_PROXY_USERNAME`, `WEBSHARE_PROXY_PASSWORD` | profile `proxy` | passed with `-s` | repository secrets |
| `YTDLP_COOKIES_BASE64` | profile `cookies` | passed with `-s` | repository secret |

The transcripts code reads `YTDLP_COOKIES_BASE64` itself and writes a private temporary file for yt-dlp (removed at exit). It is the only way to give cookies: an exported `cookies.txt` goes in with `mise run local:cookies:setup -- --file cookies.txt`, which also filters and checks it.

To use them locally:
- For one run: `FNOX_PROFILE=cookies mise run local:transcripts:manage -- --method ytdlp download-missing --limit 5`.
- With the proxy, kept on: `mise run local:profile:use -- ytdlp proxy cookies` (off again: `mise run local:profile:use -- ytdlp`).

Cookies expire, and YouTube can end the session sooner, mostly when the login is used from another address. When yt-dlp starts failing again, collect them again and run `-- --github` again.

### Download transcripts through a network, in all three places

```bash
mise run local:transcripts:download -- proxy ytdlp 3
mise run act:transcripts:download   -- proxy ytdlp 3
mise run gh:transcripts:download    -- proxy ytdlp 3
```
The arguments are the same everywhere: the network (`direct`, `proxy`, `cookies` or `proxy+cookies`), the method (`ytdlp` or `youtube_transcript_api`) and how many transcripts to stop after (3).
- `local:` runs it on your computer, with the variables from your `proxy` and `cookies` profiles. It writes `data/transcripts/` and updates your master list, like any local download.
- `act:` runs `.github/workflows/download-transcripts.yml` in Docker, with the same variables. Nothing is uploaded.
- `gh:` starts that workflow on GitHub and watches it. It needs the repository secrets (`local:proxy:setup -- --github`, `local:cookies:setup -- --github`) and tells you which one is missing. It commits nothing: the transcripts and the log are the run's artifact (**Actions → the run → Artifacts**, kept 7 days), and the run summary shows how many were downloaded. The workflow has to be on the default branch before GitHub can start it.

How the methods use the proxy:
- yt-dlp reads `PROXY_URL`.
- youtube-transcript-api uses the Webshare username and password, and tries up to 10 new addresses when one is blocked.

Webshare's free plan and its "Proxy Server" plans are data-centre addresses, which YouTube may block like GitHub's. The transcript library recommends the **Residential** plan, not "Static Residential". The setup's YouTube test tells you which case you are in.

None of these helpers ever prints a key or a password. `fnox.local.toml` is created with permissions that only you can read.

## Transcripts

`local:transcripts:manage` takes a subcommand. `stats` and `list-missing` need no method:

```bash
mise run local:transcripts:manage -- stats
```
```bash
mise run local:transcripts:manage -- list-missing
```

The rest need a method:

```bash
mise run local:transcripts:manage -- --method ytdlp download-missing --limit 5
```
```bash
mise run local:transcripts:manage -- --method ytdlp download VIDEO_ID
```
```bash
mise run local:transcripts:manage -- --method ytdlp check VIDEO_ID
```
```bash
mise run local:transcripts:compare -- VIDEO_ID
```
`local:transcripts:compare` downloads one video with both methods side by side, into `data/transcripts/compare/<id>/`.

- **The method is required.** Use `--method` or set `TRANSCRIPT_METHOD` (a `ytdlp` / `youtube-api` profile sets it). There is no default and no fallback.
- **`--limit N` stops after N downloads.**
  - Videos without captions are skipped and do not count.
  - `--max-attempts` (default 50) caps how many videos one run tries.
  - Three errors in a row stop the run, because YouTube is probably blocking you.
- **"No transcript" is remembered.**
  - The video gets `transcript_status: unavailable` and is looked up again after 1, 2, 4, 8 ... days, up to 64.
  - So repeated runs move on to other videos.
  - It is a normal outcome, not an error.
- **`--format` is what is downloaded:** `ttml` (default), `srv1`, `srt` or `vtt`.
  - `vtt` from YouTube is about 4 times bigger, because it repeats rolling caption lines.
- **`--final` is the files you keep:** a comma list from `srt,vtt,txt`, default `srt,txt`.
  - `--keep-source` also keeps the downloaded file.

For example:

```bash
mise run local:transcripts:manage -- --method ytdlp --format ttml --final srt,txt download VIDEO_ID
```

Files go to `data/transcripts/<id>.srt` and `.txt`. The list links them as `transcript_file` and `transcript_text_file`. Every run also writes `logs/transcripts.log`.

## Knowledge, chat and evaluation

These steps turn transcripts into searchable passages, answer questions, and score how well each approach works.

**Processing strategies** turn transcripts into passages:

```bash
mise run local:knowledge:manage -- strategies
```
Lists them:
- `chunks`: raw captions in 3-minute windows. It needs no model.
- `english-notes`: a model writes English notes for every 15 minutes.

```bash
mise run local:knowledge:manage -- process --strategy chunks
```
```bash
mise run local:knowledge:manage -- process --strategy english-notes --videos ID1,ID2 --provider gemini --max-requests 20
```
```bash
mise run local:knowledge:manage -- status
```

**Chat strategies** answer questions:
- `keyword`: search with the question's words.
- `multilingual`: a model first rewrites the question in English, Roman Urdu, Devanagari and Bengali.

```bash
mise run local:chat:ask -- "Which hadith number is cited about ...?" --processing english-notes --chat multilingual
```
```bash
mise run local:chat:up
```
`local:chat:up` is the browser chat at http://localhost:8000. Each person brings their own Gemini key.

**Evaluation** scores each (processing, chat) pair on `eval/questions/`. Record results worth keeping in `eval/RESULTS.md`. See [eval/README.md](eval/README.md).

```bash
mise run local:eval:manage -- questions --videos ID1,ID2
```
```bash
mise run local:eval:manage -- run --processing english-notes --chat keyword --videos ID1,ID2
```
```bash
mise run local:eval:manage -- compare
```

**Providers** answer the model questions:
- `gemini`: needs your key. The free tier allows about 20 requests a day per model.
- `queue`: the `subagents` profile. Questions are written to `data/llm/queue/pending/`, and a helper writes the answers.

Answers are cached per model, so you never pay twice for the same question. When a provider cannot answer yet, the command exits with code **75** and prints "Waiting because: ...". Run it again later and it continues.

```bash
mise run local:llm:manage -- status
```
```bash
mise run local:llm:manage -- pending
```

## The menu

```bash
mise run menu
```

A terminal menu for every action.
1. Choose the action and where to run it (local, act or GitHub).
2. Choose its options. Method, strategy and profile choices come from what is installed.
3. Check the exact `mise run ...` command, then run it.

Anything that publishes to GitHub, rebuilds the list or deletes asks first. Keys: the arrows and Enter, Esc to go back, `q` to quit.

The menu stays in sync with the `seeker` command: a test fails if a command or option cannot be reached from the menu.

## The dashboard (Tilt)

```bash
mise run local:tilt:up
```
Opens http://localhost:10350. Ctrl-C stops it, and `TILT_PORT` changes the port.

```bash
mise run local:tilt:ci
```
Runs the same checks once with no window. Exit code 0 means all green.

```bash
mise run local:workspace:graph
```
Prints which package depends on which.

A live picture of the project. Nothing is deployed: every resource is a command on your computer.
- **Packages:** one resource per package. It runs its tests in dependency order and again when its code, or code it depends on, changes.
- **Data:** reports on the list and the transcripts.
- **Settings:** the active profile with a "Switch fnox profile" button, and the methods with a "Set a method" button.
- **Manual resources:** press the trigger arrow on update, rebuild, transcripts download and compare, wheel build, act and Docker diagnose.
- **The chat:** a `chat` resource.

Nothing on the dashboard publishes to GitHub. Details are in [docs/architecture.md](docs/architecture.md).

## Docker (only for `act:` tasks)

```bash
mise run docker:start
```
Starts Colima (or Docker Desktop) and waits until it is ready.

```bash
mise run docker:stop
```
Removes this project's containers and volumes, then stops Docker. It leaves Docker running if other containers are in use.

```bash
mise run docker:cleanup
```
Removes leftovers only and keeps Docker running.

```bash
mise run docker:diagnose
```
Compares your computer's CPU, memory and disk with what Docker has, and says how to change it.

```bash
mise run act:list
```
Lists the workflows `act` can run.

`act:` tasks start Docker if it is off. They also:
- remove old leftovers first
- always clean up afterwards, even after an error or Ctrl-C
- stop Docker only if they started it

act needs about 2+ CPUs, 4+ GB of memory and 30+ GB of disk.

## Cleaning up (nuke)

```bash
mise run nuke -- --dry-run
```
Shows what would be removed.

```bash
mise run nuke
```
Removes `.venv`, `.act/` and this project's Docker containers, volumes and image. It asks first.

```bash
mise run nuke -- --all
```
Also removes the uv cache, the act tool cache, this project's mise tools, `fnox.local.toml` and `.fnox-profile`.

Everything act creates is labelled `project=adam-seeker-metadata` or lives in `.act/` (see `.actrc`), so nuke removes only what this project made. Docker itself is never uninstalled.

## GitHub Actions

| Workflow | When | What it does |
|---|---|---|
| Update Video List (`update-videos.yml`) | daily at 06:00 UTC, and by hand | `mise run local:videos:update`. Only when videos were **added**: commits `data/videos_master.json` and `logs/`, and comments on the open "📺 New Videos Available for Review" issue (or opens it). |
| Rebuild Video List (`rebuild-videos.yml`) | by hand only | `mise run local:videos:rebuild`, commits, opens a summary issue |

How the workflows behave:
- **They share one concurrency group,** so they never push at the same time.
- **They have no `push:` trigger,** so merging code never starts a run.
- **They install only the CLI** (`mise run setup:cli`), not the chat app.
- **They ask for `contents: write` and `issues: write`,** so they work on forks and new repositories without changing settings.
- **The logs are uploaded with every run** and kept for 30 days.

A run that finds no new videos commits nothing and comments nowhere. The `last_updated` date and log lines change on every run, but they do not count.

**Setting it up on your own copy** (enable Actions and Issues, add the secret, run it once) is in [README.md](README.md#set-it-up-on-your-own-copy-a-fork).

**Watching runs:**

```bash
mise run gh:list
```
Lists recent runs.

```bash
gh run view --log
```
Shows the log of a run.

Or open the **Actions** tab on GitHub.

## Reviewing new videos

1. GitHub comments on the review issue when new videos arrive.
2. Pull the changes:
   ```bash
   git pull
   ```
3. Categorize the new videos:
   ```bash
   mise run local:videos:manage interactive
   ```
   Or use `categorize` for one video.
4. Commit and push `data/videos_master.json`, then close the issue.

When reviewing:
- Keep the 1-10 scores consistent.
- Write notes your future self will understand.

## Logs

```bash
tail -f logs/update_master.log
```

Log files:
- `logs/update_master.log`
- `logs/rebuild_master.log`
- `logs/transcripts.log` (git-ignored)

The workflow commits the first two when it commits new videos.

For problems, see the table in [README.md](README.md#when-something-goes-wrong).

## Building and adding SDKs

```bash
mise run build:sdks
```
Builds each SDK as its own wheel into `dist/sdks`, then checks each one installs and works on its own.

```bash
mise run build:apps
```
Does the same for the apps, into `dist/apps`.

```bash
mise run sdk:new -- rag --plugin video_sources
```
Creates a new SDK, `sdks/rag`, with a plugin skeleton.

How the code fits together is in [docs/architecture.md](docs/architecture.md).

Before a pull request:
- Run `mise run test`.
- If you changed dependencies, run `uv lock` and commit `uv.lock`.
