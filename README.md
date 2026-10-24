# adam-seeker-metadata

A list of every video on the YouTube channel [@AdamSeekerOfficial](https://www.youtube.com/@AdamSeekerOfficial), plus tools to:
- keep the list up to date (GitHub does this every day)
- download the transcripts
- search them and chat with them

## What is in this repository

| What | Where |
|---|---|
| The video list: title, date, link, your categories and notes, transcript status | `data/videos_master.json` |
| The tools (a `seeker` command, a terminal menu, a chat app) | `sdks/`, `apps/` |
| The daily GitHub job that adds new videos | `.github/workflows/update-videos.yml` |
| Logs of every update | `logs/` |

Transcripts are **not** stored in git because they are too big. You download them with one command (below).

**Only want the data?** Open [`data/videos_master.json`](data/videos_master.json), or download it from
https://raw.githubusercontent.com/kbhatiya999/adam-seeker-metadata/main/data/videos_master.json. You need nothing else.

---

## Run it on your computer

This works on macOS and Linux. On Windows, install WSL (Ubuntu) and follow the Linux steps inside it.

You install only **git** and **mise** yourself. mise then installs everything else into this project: Python, uv, and the other tools. You do not need to install Python.

### Step 1: install git and mise

macOS, with [Homebrew](https://brew.sh):
```bash
brew install git mise
```

Linux:
```bash
curl https://mise.run | sh
```

Then open a new terminal and check:
```bash
mise --version
```
If it says "command not found", add `~/.local/bin` to your PATH. The installer prints how to do that.

### Step 2: get the code

```bash
git clone https://github.com/kbhatiya999/adam-seeker-metadata.git
```
```bash
cd adam-seeker-metadata
```

### Step 3: install the tools and the Python packages

```bash
mise trust
```
```bash
mise install
```
```bash
mise run install
```

What each one does:
- `mise trust`: tells mise you trust this folder's settings file. mise asks this once per folder.
- `mise install`: downloads the tools. The first time takes a few minutes.
- `mise run install`: installs the Python packages into `.venv`. It also checks for Docker, which is optional and only needed for the `act:` tasks. If Docker is missing, it says so and continues. On macOS it offers to install it.

### Step 4: check that it works

```bash
mise run test
```
```bash
mise run local:videos:manage report
```

All tests should pass. A few are skipped until you have transcripts. The report prints how many videos there are and lists the newest ones.

### Step 5: use it

The easiest way is the menu:
```bash
mise run menu
```
- Use the arrow keys and Enter to choose, Esc to go back, and `q` to quit.
- The menu shows the exact command before it runs anything.
- It asks before anything that publishes to GitHub or deletes.

Or type the commands yourself. No key or account is needed for any of these:

| I want to... | Command |
|---|---|
| See a report of the list | `mise run local:videos:manage report` |
| Add new videos from YouTube to the list | `mise run local:videos:update` |
| Download 5 missing transcripts | `mise run local:transcripts:manage -- --method ytdlp download-missing --limit 5` |
| See how many transcripts I have | `mise run local:transcripts:manage -- stats` |
| Put videos into categories, one by one | `mise run local:videos:manage interactive` |
| Make the transcripts searchable (no AI) | `mise run local:knowledge:manage -- process --strategy chunks` |
| Chat with the videos in a browser | `mise run local:chat:up` (see [Chat with the videos](#chat-with-the-videos)) |
| See everything in a live dashboard | `mise run local:tilt:up`, then open http://localhost:10350 |
| See every task | `mise tasks` |

The `--` in a command means "the rest is for the tool, not for mise".

You may see `Warning: Secret 'YOUTUBE_API_KEY' not found`. That is fine: without a YouTube key, the tools use yt-dlp instead. See [Keys](#keys-optional).

---

## Chat with the videos

1. Download some transcripts:
   ```bash
   mise run local:transcripts:manage -- --method ytdlp download-missing --limit 5
   ```
2. Make them searchable. This step needs no key:
   ```bash
   mise run local:knowledge:manage -- process --strategy chunks
   ```
3. Start the chat:
   ```bash
   mise run local:chat:up
   ```
   It opens http://localhost:8000. Press Ctrl-C in the terminal to stop it.
4. The chat asks for **your own Gemini key**. Get one free at https://aistudio.google.com/apikey: sign in, then click "Create API key". Paste it into the chat. It stays in your browser and is never saved on the server.
5. Pick a strategy at the top, then ask a question or click one of the example questions. Answers name the video and the time.

**Better answers:** the `english-notes` strategy has a model write English notes for each part of a video. That suits these transcripts, which are in Hindi/Urdu written in Devanagari script. It needs a Gemini key on your computer (see [Keys](#keys-optional)):
```bash
mise run local:knowledge:manage -- process --strategy english-notes --provider gemini --max-requests 20
```
The free Gemini tier allows about 20 requests a day per model. When the quota runs out, the command stops with "Waiting because: ...". Run it again the next day, and it continues where it stopped.

---

## Keys (optional)

Everything above works without keys. Keys and a proxy make three things better:

| Key | What it gives you | How to get it |
|---|---|---|
| YouTube Data API key | Faster updates, with exact upload dates | `mise run local:apikey:setup` |
| Gemini API key | Model-based processing from the command line (`english-notes`, `ask`, `eval`) | `mise run local:apikey:gemini` |
| Webshare proxy | Transcripts where YouTube blocks your address (it blocks GitHub's) | `mise run local:proxy:setup` |
| YouTube cookies (optional) | Another way past YouTube's "not a bot" check, for yt-dlp only. Use a throwaway Google account | `mise run local:cookies:setup` |

Try the proxy or the cookies in all three places with the same command: `mise run local:transcripts:download -- proxy ytdlp 3`, then `act:` and `gh:` instead of `local:` (details in [README_AUTOMATION.md](README_AUTOMATION.md)).

- Both keys are free. The proxy is a Webshare account.
- Each helper opens the right page, checks what you paste with one test call, and saves it **encrypted** in `fnox.toml`.
- The proxy is saved as a profile called `proxy`, and the cookies as a profile called `cookies`, so they are used only when you pick them (see [Settings](#settings-fnox-profiles)).
- `fnox.toml` is committed, but only as ciphertext (age). Two keys can read it: your own (`~/.config/fnox/age.txt`) and the one in the GitHub secret `FNOX_AGE_KEY`. So your computer, act and GitHub all read the same values. Run `mise run local:secrets:init` once first; the helpers then offer to publish the change straight to main. Details: [Encrypted secrets](README_AUTOMATION.md#encrypted-secrets-age).
- Never put a key anywhere else, and never commit a plain value.
- The chat app does not use this saved Gemini key. Everyone types their own key in the browser.

### Settings (fnox profiles)

Settings choose *how* things are done:
- which tool fetches videos and transcripts: `ytdlp` or `youtube-api`
- which model runs the AI steps: `subagents`, `gemini` or `gemini-lite`

You pick them by name:

```bash
mise run local:profile:show
```
```bash
mise run local:profile:use -- ytdlp gemini-lite
```
```bash
mise run local:profile:use
```

- `local:profile:show` shows what is active. It shows whether each key is set, never its value.
- `local:profile:use -- ytdlp gemini-lite` picks one methods profile and one model profile.
- `local:profile:use` with no names goes back to the default.

Every task uses the profile you pick, whether you run it from the terminal, the menu or the Tilt dashboard. The details are in [README_AUTOMATION.md](README_AUTOMATION.md#fnox-profiles).

---

## Three places to run the same job

The same job can run in three places. Try them in this order:

| Tasks starting with | Run where | What you need | Changes GitHub? |
|---|---|---|---|
| `local:` | directly on your computer | nothing more | no (only your files) |
| `act:` | the real GitHub workflow, in Docker on your computer | Docker | no: commit, push and issue steps are skipped |
| `gh:` | the real workflow, on GitHub | `gh auth login`, and push access to the repository | **yes**: commits, and comments on issues |

For example:
```bash
mise run local:videos:update
```
```bash
mise run act:videos:update
```
```bash
mise run gh:videos:update
```

- `act:` tasks start Docker if it is off and clean up afterwards. They stop Docker again if they were the one that started it.
- `gh:` tasks run on your current branch. Use `REF=main mise run gh:videos:update` to pick a different one. They wait and show the run's progress. `mise run gh:list` lists recent runs.

---

## GitHub: the daily update

Every day at 06:00 UTC, GitHub runs **Update Video List**. It:
1. installs the tools (only what the `seeker` command needs)
2. runs `mise run local:videos:update`, the same command you run at home
3. **if there are new videos:** commits `data/videos_master.json` and `logs/`, and comments on the open issue "📺 New Videos Available for Review". If you closed that issue, it opens a new one.
4. **if there are no new videos:** commits nothing and opens nothing. The logs are still kept with the run for 30 days.

**Rebuild Video List** runs only when you start it. It fetches the whole list again and keeps your categories and notes. See [README_REBUILD.md](README_REBUILD.md).

### Set it up on your own copy (a fork)

1. Click **Fork** on GitHub. Then clone *your* fork in [Step 2](#step-2-get-the-code).
2. Open your fork's **Actions** tab and click "I understand my workflows, go ahead and enable them". Forks start with workflows switched off, and the daily run starts only after this.
3. Turn on Issues: **Settings → General → Features → Issues**. Forks start without Issues, and the workflow posts its review notes there.
4. Optional: keys. Without any, the workflow uses yt-dlp, which also works. The secrets in `fnox.toml` are encrypted for *our* keys, so a fork cannot read them. Pick one:
   - **your own encrypted secrets** (the same setup as here): run `mise run local:secrets:init` (your key), `mise run local:secrets:ci-key` (sets your fork's `FNOX_AGE_KEY` secret), then the key helpers ([Keys](#keys-optional)), and `mise run local:secrets:publish`. Delete our old encrypted values first: they can't be decrypted with your keys.
   - **a plain repository secret** for the YouTube key: **Settings → Secrets and variables → Actions → New repository secret**, name it `YOUTUBE_API_KEY`, or run the command below, which asks for the key without showing it. It is used only when there is no `FNOX_AGE_KEY`.
     ```bash
     gh secret set YOUTUBE_API_KEY
     ```
5. Run it once by hand to check. Either:
   - go to **Actions → Update Video List → Run workflow**, or
   - sign in to `gh` once, then run the update:
     ```bash
     gh auth login
     ```
     ```bash
     mise run gh:videos:update
     ```

The workflows ask GitHub for exactly what they need: permission to commit and permission to write issues. You do not need to change any other setting.

**Choosing the method on GitHub (optional):** by default, GitHub uses the YouTube API if the secret is set, and yt-dlp otherwise. To fix one:
```bash
mise run gh:method:set -- master-list ytdlp
```
`mise run all:method:show` shows what your computer, act and GitHub each use.

### Reviewing new videos

1. Pull the changes:
   ```bash
   git pull
   ```
2. Categorize the new videos:
   ```bash
   mise run local:videos:manage interactive
   ```
3. Commit and push `data/videos_master.json`.
4. Close the review issue. The next new video opens a fresh one.

---

## When something goes wrong

| What you see | What to do |
|---|---|
| `mise: command not found` | Open a new terminal. On Linux, add `~/.local/bin` to your PATH. |
| mise says the config file is not trusted | `mise trust` |
| `uv: command not found` or `seeker: command not found` | Run things through `mise run ...`. To type `uv` yourself, see "activate" in the [mise getting started guide](https://mise.jdx.dev/getting-started.html). |
| `Warning: Secret 'YOUTUBE_API_KEY' not found` | Harmless. Without a key, yt-dlp is used. |
| An `act:` task says Docker is missing | Install Colima (`brew install colima docker`) or Docker Desktop. `mise run docker:diagnose` checks Docker's memory and disk. |
| Transcripts: `HTTP Error 429` or "Sign in to confirm you're not a bot" | YouTube is slowing you down. Wait an hour, use a smaller `--limit`, or try `--method youtube_transcript_api`. A run stops by itself after 3 errors in a row. On GitHub it is always blocked; there you need a proxy (`mise run local:proxy:setup`). |
| "no transcript available, will look again after ..." | Normal. The video has no captions yet. It is checked again after 1, 2, 4, 8 ... days. |
| "Waiting because: ..." (exit code 75) | A model step is waiting. With Gemini, the free daily quota is used up: run again tomorrow, or switch model with `mise run local:profile:use -- gemini-lite`. With the `subagents` profile, the questions wait in `data/llm/queue/pending/`. |
| The chat says no videos are processed | Do steps 1 and 2 of [Chat with the videos](#chat-with-the-videos). |
| A `gh:` task fails | Run `gh auth login`. In a clone with two remotes (fork and original), run `gh repo set-default` and pick your fork. |
| The workflow fails at "Create notification issue" | Issues are off. Turn them on: **Settings → General → Features → Issues**. |
| The daily run never starts on your fork | Enable workflows in the **Actions** tab. GitHub also pauses daily runs in public repositories after 60 days without commits; turn it back on in the Actions tab. |

Logs on your computer:
- `logs/update_master.log`
- `logs/rebuild_master.log`
- `logs/transcripts.log`

On GitHub, open the run in the **Actions** tab.

---

## Clean up

```bash
mise run nuke -- --dry-run
```
```bash
mise run nuke
```
```bash
mise run nuke -- --all
```

- `--dry-run` only shows what would be removed.
- `nuke` removes `.venv` and this project's Docker leftovers. It asks first.
- `--all` also removes the caches, the tools and `fnox.local.toml`, which holds your own settings. Your age key in `~/.config/fnox/` is never touched.

Docker itself is never uninstalled.

---

## More documentation

| Document | What it covers |
|---|---|
| [README_AUTOMATION.md](README_AUTOMATION.md) | Every task in detail: videos, methods, transcripts, profiles, menu, dashboard, chat, Docker |
| [README_REBUILD.md](README_REBUILD.md) | Rebuilding the whole list safely |
| [docs/architecture.md](docs/architecture.md) | How the code is organised: SDKs, apps, plugins |
| [docs/primer/](docs/primer/) | Short lessons for new contributors |
| [eval/README.md](eval/README.md) | The evaluation questions and how strategies are scored |
| [AGENTS.md](AGENTS.md) | The rules for AI coding agents, also a dense summary for people |

Before you open a pull request, run:
```bash
mise run test
```

---

## Transcripts with plain yt-dlp (no setup)

If you only want a few transcripts and do not want to install this project, [yt-dlp](https://github.com/yt-dlp/yt-dlp) alone can do it. These transcripts are not linked into the video list.

One video:
```bash
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download "https://www.youtube.com/watch?v=VIDEO_ID"
```

Every video on the channel:
```bash
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download "https://www.youtube.com/@AdamSeekerOfficial/videos"
```

Every live stream:
```bash
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download "https://www.youtube.com/@AdamSeekerOfficial/streams"
```

A list of videos (one link per line in `video_links.txt`):
```bash
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download --batch-file video_links.txt
```

Most videos have only automatic captions in Hindi. Use `--sub-langs "hi.*,en.*"` to get those, or run `--list-subs` first to see what a video has.
