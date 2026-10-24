#!/usr/bin/env bash
# Guided setup for the YouTube Data API v3 key.
# A key can only be created from your own Google account, so this cannot fetch one for you:
# it walks you through the console, validates the key you paste, and saves it
# encrypted (age) in the committed fnox.toml (scripts/secrets.py). The key is never printed or put on a command line.
set -u
cd "$(dirname "$0")/.." || exit 1

KEY_URL="https://console.cloud.google.com/apis/credentials"
LIB_URL="https://console.cloud.google.com/apis/library/youtube.googleapis.com"

# Print the command before running it (commands that would contain the key are shown redacted)
show() { printf '  \033[2m$ %s\033[0m\n' "$*" >&2; }

has_key() { [ -n "$(fnox get YOUTUBE_API_KEY 2>/dev/null)" ]; }

if has_key; then
  read -r -p "A key is already saved. Replace it? [y/N] " a
  case "$a" in [yY]*) ;; *) echo "Keeping existing key."; exit 0 ;; esac
fi

key=""
from_gcloud=0

gcloud_create_key() {
  local acct project out name
  acct="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1)"
  if [ -z "$acct" ]; then
    echo "Sign in to Google (opens your browser)..."
    show gcloud auth login
    gcloud auth login || return 1
    acct="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)"
  fi
  echo "Signed in as: $acct"
  project="$(gcloud config get-value project 2>/dev/null)"
  echo "Your projects:"; show gcloud projects list --format='table(projectId,name)'; gcloud projects list --format='table(projectId,name)' 2>/dev/null | head -15
  read -r -p "Project ID to use [${project:-none}] (enter a NEW id to create it): " p
  project="${p:-$project}"
  [ -n "$project" ] || { echo "No project given."; return 1; }
  if ! gcloud projects describe "$project" >/dev/null 2>&1; then
    read -r -p "Project '$project' does not exist. Create it? [y/N] " c
    case "$c" in [yY]*) show gcloud projects create "$project"; gcloud projects create "$project" || return 1 ;; *) return 1 ;; esac
  fi
  echo "Enabling YouTube Data API v3 on $project..."
  show gcloud services enable youtube.googleapis.com --project "$project"
  gcloud services enable youtube.googleapis.com --project "$project" || return 1
  echo "Creating an API key restricted to the YouTube Data API..."
  show gcloud services api-keys create --display-name=adam-seeker-metadata --api-target=service=youtube.googleapis.com --project "$project" --format=json '(output captured, not printed)'
  # stderr is hidden too: gcloud prints the created key there
  out="$(gcloud services api-keys create --display-name=adam-seeker-metadata \
        --api-target=service=youtube.googleapis.com --project "$project" --format=json 2>/dev/null)" || { echo "key creation failed; re-run the command above to see the error"; return 1; }
  key="$(printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("response") or d).get("keyString",""))' 2>/dev/null)"
  if [ -z "$key" ]; then
    name="$(printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("response") or d).get("name",""))' 2>/dev/null)"
    if [ -n "$name" ]; then show gcloud services api-keys get-key-string "$name" --format='value(keyString)' '(output captured, not printed)'; key="$(gcloud services api-keys get-key-string "$name" --format='value(keyString)' 2>/dev/null)"; fi
  fi
  [ -n "$key" ] || { echo "Could not read the new key; get it from $KEY_URL"; return 1; }
  from_gcloud=1
}

if command -v gcloud >/dev/null 2>&1 && gcloud --version >/dev/null 2>&1; then
  read -r -p "Create the key automatically with gcloud (you sign in with your own Google account)? [Y/n] " g
  case "$g" in [nN]*) ;; *) gcloud_create_key || { echo "gcloud path failed; falling back to the manual steps."; key=""; } ;; esac
else
  echo "(gcloud not available: run 'mise run install' to get it; using the manual steps.)"
fi

if [ -z "$key" ]; then
cat <<EOF2
Get a YouTube Data API v3 key (free; the daily quota of 10,000 units is plenty for this repo):

  1. Sign in at Google Cloud Console and pick or create a project:  https://console.cloud.google.com/projectcreate
  2. Enable "YouTube Data API v3":                                   $LIB_URL
  3. Create the key: Credentials -> Create credentials -> API key:   $KEY_URL
  4. Recommended: edit the key -> "API restrictions" -> Restrict key -> YouTube Data API v3.
  5. Copy the key and paste it below.
EOF2

if [ -t 0 ] && [ "$(uname -s)" = Darwin ]; then
  read -r -p "Open the Google Cloud pages in your browser now? [Y/n] " o
  case "$o" in [nN]*) ;; *) show open "$LIB_URL"; open "$LIB_URL"; show open "$KEY_URL"; open "$KEY_URL" ;; esac
fi

printf 'Paste your API key (input hidden): '
read -rs key; echo
key="$(printf '%s' "$key" | tr -d '[:space:]')"
[ -n "$key" ] || { echo "No key entered."; exit 1; }
fi

# Validate with one cheap call (1 quota unit); the key goes in a header via stdin, not argv/URL.
# New keys can take a minute to propagate, so retry when we just created it
attempts=1; [ "$from_gcloud" = 1 ] && attempts=8
for i in $(seq "$attempts"); do
  [ "$i" = 1 ] && show "printf 'header = \"x-goog-api-key: <hidden>\"' | curl -s -K - 'https://www.googleapis.com/youtube/v3/videos?part=id&id=dQw4w9WgXcQ'"
  resp="$(printf 'header = "x-goog-api-key: %s"\n' "$key" | curl -s -K - \
    'https://www.googleapis.com/youtube/v3/videos?part=id&id=dQw4w9WgXcQ')"
  printf '%s' "$resp" | grep -q '"items"' && break
  if [ "$i" -lt "$attempts" ]; then echo "Key not active yet, retrying in 10s ($i/$attempts)..."; sleep 10; fi
done
if ! printf '%s' "$resp" | grep -q '"items"'; then
  reason="$(printf '%s' "$resp" | sed -n 's/.*"message": *"\([^"]*\)".*/\1/p' | head -1)"
  echo "❌ Key rejected by the YouTube API: ${reason:-no valid response}"
  echo "   Check that YouTube Data API v3 is enabled for the key's project and the key restrictions allow it."
  exit 1
fi
echo "✅ Key works"

show "printf '%s' <hidden> | python3 scripts/secrets.py set YOUTUBE_API_KEY   (encrypted into fnox.toml)"
printf '%s' "$key" | python3 scripts/secrets.py set YOUTUBE_API_KEY || exit 1
echo "Saved (encrypted in fnox.toml; local, act and GitHub all read it from there)."
if [ -t 0 ]; then python3 scripts/secrets.py publish || true
else echo "Publish it for act and GitHub: mise run local:secrets:publish"; fi
echo "Verify: mise run local:videos:update  (log should say it used the YouTube Data API)"
