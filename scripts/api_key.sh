#!/usr/bin/env bash
# Guided setup for the YouTube Data API v3 key.
# A key can only be created from your own Google account, so this cannot fetch one for you:
# it walks you through the console, validates the key you paste, and saves it to the
# git-ignored fnox.local.toml. The key is never printed or put on a command line.
set -u

KEY_URL="https://console.cloud.google.com/apis/credentials"
LIB_URL="https://console.cloud.google.com/apis/library/youtube.googleapis.com"
LOCAL_FILE="fnox.local.toml"

has_key() { grep -q '^YOUTUBE_API_KEY' "$LOCAL_FILE" 2>/dev/null; }

if has_key; then
  read -r -p "A key is already saved in $LOCAL_FILE. Replace it? [y/N] " a
  case "$a" in [yY]*) ;; *) echo "Keeping existing key."; exit 0 ;; esac
fi

cat <<EOF2
Get a YouTube Data API v3 key (free; the daily quota of 10,000 units is plenty for this repo):

  1. Sign in at Google Cloud Console and pick or create a project:  https://console.cloud.google.com/projectcreate
  2. Enable "YouTube Data API v3":                                   $LIB_URL
  3. Create the key: Credentials -> Create credentials -> API key:   $KEY_URL
  4. Recommended: edit the key -> "API restrictions" -> Restrict key -> YouTube Data API v3.
  5. Copy the key and paste it below.

  (CLI alternative if you use gcloud:  gcloud services enable youtube.googleapis.com &&
   gcloud services api-keys create --display-name=adam-seeker-metadata --api-target=service=youtube.googleapis.com)
EOF2

if [ -t 0 ] && [ "$(uname -s)" = Darwin ]; then
  read -r -p "Open the Google Cloud pages in your browser now? [Y/n] " o
  case "$o" in [nN]*) ;; *) open "$LIB_URL"; open "$KEY_URL" ;; esac
fi

printf 'Paste your API key (input hidden): '
read -rs key; echo
key="$(printf '%s' "$key" | tr -d '[:space:]')"
[ -n "$key" ] || { echo "No key entered."; exit 1; }

# Validate with one cheap call (1 quota unit); the key goes in a header via stdin, not argv/URL.
resp="$(printf 'header = "x-goog-api-key: %s"\n' "$key" | curl -s -K - \
  'https://www.googleapis.com/youtube/v3/videos?part=id&id=dQw4w9WgXcQ')"
if ! printf '%s' "$resp" | grep -q '"items"'; then
  reason="$(printf '%s' "$resp" | sed -n 's/.*"message": *"\([^"]*\)".*/\1/p' | head -1)"
  echo "❌ Key rejected by the YouTube API: ${reason:-no valid response}"
  echo "   Check that YouTube Data API v3 is enabled for the key's project and the key restrictions allow it."
  exit 1
fi
echo "✅ Key works"

umask 077
KEY="$key" python3 - "$LOCAL_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; key = os.environ["KEY"]
line = f'YOUTUBE_API_KEY = {{ default = "{key}" }}'
text = open(path).read() if os.path.exists(path) else ""
if re.search(r'^YOUTUBE_API_KEY\s*=.*$', text, re.M):
    text = re.sub(r'^YOUTUBE_API_KEY\s*=.*$', lambda m: line, text, flags=re.M)
else:
    if "[secrets]" not in text:
        text += ("\n" if text and not text.endswith("\n") else "") + "[secrets]\n"
    text = text.replace("[secrets]\n", "[secrets]\n" + line + "\n", 1)
open(path, "w").write(text)
PY
chmod 600 "$LOCAL_FILE"
echo "Saved to $LOCAL_FILE (git-ignored, mode 600)."

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  read -r -p "Also store it as the GitHub Actions secret YOUTUBE_API_KEY for this repo? [y/N] " g
  case "$g" in
    [yY]*) printf '%s' "$key" | gh secret set YOUTUBE_API_KEY && echo "✅ GitHub secret set" ;;
    *) echo "Skipped. Later: mise run local:apikey:setup, or set it in repo Settings -> Secrets and variables -> Actions." ;;
  esac
fi
echo "Verify: mise run local:videos:update  (log should say it used the YouTube Data API)"
