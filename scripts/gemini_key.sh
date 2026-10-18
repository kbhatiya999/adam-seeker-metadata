#!/usr/bin/env bash
# Gemini API key (Google AI Studio) for the model tools run with --provider gemini (the daily processing run).
# The chat app does not use it: it asks each user for their own key in the browser.
#   gemini_key.sh            open AI Studio, paste the key (hidden), check it, save it to fnox.local.toml
#   gemini_key.sh --stdin    read the key from standard input instead of prompting
#   gemini_key.sh --check    check the key that is already saved
set -euo pipefail
cd "$(dirname "$0")/.."
URL="https://aistudio.google.com/apikey"
LOCAL_FILE="fnox.local.toml"
show() { printf '  \033[2m$ %s\033[0m\n' "$*" >&2; }

check_key() { # the key goes in a header read from a pipe, never on a command line
  local out code body
  show "curl -H 'x-goog-api-key: <hidden>' https://generativelanguage.googleapis.com/v1beta/models"
  out="$(curl -s -m 20 -w '\n%{http_code}' -H @<(printf 'x-goog-api-key: %s\n' "$1") \
         'https://generativelanguage.googleapis.com/v1beta/models?pageSize=200')"
  code="${out##*$'\n'}"; body="${out%$'\n'*}"
  if [ "$code" != 200 ]; then
    printf '❌ The key was rejected (HTTP %s): %s\n' "$code" \
      "$(printf '%s' "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("error",{}).get("message","")[:200])' 2>/dev/null)"
    return 1
  fi
  printf '%s' "$body" | python3 -c '
import json, sys
models = [m["name"].split("/")[-1] for m in json.load(sys.stdin).get("models", [])
          if "generateContent" in m.get("supportedGenerationMethods", [])]
flash = sorted(m for m in models if "flash" in m)
print("✅ The key works: {} models can generate text; flash models: {}".format(len(models), ", ".join(flash) or "none"))'
}

save_key() {
  show "edit $LOCAL_FILE: GEMINI_API_KEY = { default = \"<hidden>\" } under [secrets]  (git-ignored, mode 600)"
  KEY="$1" python3 - "$LOCAL_FILE" <<'PY'
import os, re, sys
path, key = sys.argv[1], os.environ["KEY"]
text = open(path).read() if os.path.exists(path) else ""
text = re.sub(r'^GEMINI_API_KEY\s*=.*\n?', '', text, flags=re.M)
if "[secrets]" not in text:
    text += ("\n" if text and not text.endswith("\n") else "") + "[secrets]\n"
text = text.replace("[secrets]\n", '[secrets]\nGEMINI_API_KEY = { default = "%s" }\n' % key, 1)
open(path, "w").write(text)
PY
  chmod 600 "$LOCAL_FILE"
}

case "${1:-}" in
  --check)
    key="$(fnox get GEMINI_API_KEY 2>/dev/null || true)"
    [ -n "$key" ] || { echo "No GEMINI_API_KEY saved yet: mise run local:apikey:gemini"; exit 1; }
    check_key "$key"; exit $? ;;
  --stdin)
    IFS= read -r key || true ;;
  "")
    echo "Create a key in Google AI Studio (sign in with your Google account, then \"Create API key\"):"
    echo "  $URL"
    echo "If that page does not open, go to https://aistudio.google.com and click \"Get API key\" in the sidebar."
    if command -v open >/dev/null; then show open "$URL"; open "$URL" || true; fi
    printf 'Paste the key (input hidden): '; IFS= read -rs key; echo ;;
  *) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
key="$(printf '%s' "$key" | tr -d '[:space:]')"
[ -n "$key" ] || { echo "No key given."; exit 1; }
check_key "$key" || exit 1
save_key "$key"
echo "✅ Saved. Used by: seeker knowledge process / ask / eval run with --provider gemini (they run through fnox)."
echo "   Keep it private: restrict it to the Generative Language API in the Google Cloud console if you can."
