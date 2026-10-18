#!/usr/bin/env bash
# Webshare proxy for transcripts, so YouTube sees a proxy's address instead of a blocked one (GitHub's runners are
# blocked: "Sign in to confirm you're not a bot"). Uses Webshare's ROTATING endpoint (p.webshare.io:80, username
# + "-rotate"): every request may leave from a different address, so one blocked address does not stop a run.
#   proxy_setup.sh            open Webshare, ask for the proxy username and password (hidden), test, save
#   proxy_setup.sh --check    test the saved proxy again (the proxy itself, then YouTube with both methods)
#   proxy_setup.sh --github   copy the saved proxy to the GitHub repository secrets (for a transcripts workflow)
# Saved in the git-ignored fnox.local.toml as the local profile `proxy` (not at the top level), so your own runs go
# direct unless you pick it: `mise run local:profile:use -- ytdlp proxy` or `FNOX_PROFILE=proxy mise run ...`.
# The password never appears on a command line, in the output or in the logs.
set -euo pipefail
cd "$(dirname "$0")/.."
LOCAL_FILE="fnox.local.toml"
DASHBOARD="https://dashboard.webshare.io/"
VIDEO="HyF6HAlId7g"   # has automatic captions; downloads fine from a home address, blocked from GitHub (2026-10-18)
NAMES=(WEBSHARE_PROXY_USERNAME WEBSHARE_PROXY_PASSWORD PROXY_URL)
show() { printf '  \033[2m$ %s\033[0m\n' "$*" >&2; }

proxy_url() { # rotating endpoint URL, user and password URL-encoded
  USER_="$1" PASS_="$2" python3 -c '
import os, urllib.parse as u
q = lambda s: u.quote(s, safe="")
print("http://%s-rotate:%s@p.webshare.io:80/" % (q(os.environ["USER_"]), q(os.environ["PASS_"])))'
}

test_proxy() { # 1. does the proxy accept the login? Credentials go to curl through stdin, not the command line.
  local ip u="${1//\\/\\\\}" p="${2//\\/\\\\}"   # escape \ and " for curl's config syntax
  u="${u//\"/\\\"}"; p="${p//\"/\\\"}"
  show "curl --proxy http://p.webshare.io:80 --proxy-user '<username>-rotate:<hidden>' https://ipv4.webshare.io/"
  if ip="$(printf 'proxy = "http://p.webshare.io:80"\nproxy-user = "%s-rotate:%s"\n' "$u" "$p" \
           | curl -s -m 30 -f -K - https://ipv4.webshare.io/)"; then
    echo "✅ The proxy works: requests leave from $ip"
  else
    echo "❌ The proxy refused the connection. Check the username and password on the Webshare proxy list page"
    echo "   (Authentication method: Username/Password)."
    return 1
  fi
}

test_youtube() { # 2. does YouTube answer through it? Same check as `seeker transcripts check`, once per method.
  local ok=0 method out
  for method in ytdlp youtube_transcript_api; do
    show "seeker transcripts --method $method check $VIDEO   (through the proxy)"
    if out="$(WEBSHARE_PROXY_USERNAME="$1" WEBSHARE_PROXY_PASSWORD="$2" PROXY_URL="$3" \
              uv run --no-sync seeker transcripts --method "$method" check "$VIDEO" 2>&1 | tail -1)" \
       && [ "$out" = "available" ]; then
      echo "✅ $method: YouTube answers through the proxy"
      ok=$((ok + 1))
    else
      echo "❌ $method: ${out:0:200}"
    fi
  done
  if [ "$ok" = 0 ]; then
    echo "YouTube blocks these proxy addresses too. Webshare's free plan and \"Proxy Server\" plans are data-centre"
    echo "addresses, which YouTube treats like GitHub's. The transcript library recommends Webshare's \"Residential\""
    echo "plan (not \"Static Residential\"). After changing the plan, run: mise run local:proxy:setup -- --check"
    return 1
  fi
}

save_local() {
  show "edit $LOCAL_FILE: [profiles.proxy.secrets] ${NAMES[*]} = <hidden>  (git-ignored, mode 600)"
  USER_="$1" PASS_="$2" URL_="$3" python3 - "$LOCAL_FILE" <<'PY'
import json, os, re, sys
path = sys.argv[1]
text = open(path).read() if os.path.exists(path) else ""
# drop an old [profiles.proxy.secrets] section (up to the next [header] or the end)
text = re.sub(r'^(?:# Webshare rotating proxy.*\n)?\[profiles\.proxy\.secrets\]\n(?:(?!\[).*\n?)*', '', text,
              flags=re.M).rstrip("\n")
values = {"WEBSHARE_PROXY_USERNAME": os.environ["USER_"], "WEBSHARE_PROXY_PASSWORD": os.environ["PASS_"],
          "PROXY_URL": os.environ["URL_"]}
section = ["", "# Webshare rotating proxy (mise run local:proxy:setup). Used only when you pick the `proxy` profile.",
           "[profiles.proxy.secrets]"] + ["%s = { default = %s }" % (k, json.dumps(v)) for k, v in values.items()]
open(path, "w").write((text + "\n" if text else "") + "\n".join(section) + "\n")
PY
  chmod 600 "$LOCAL_FILE"
}

load_saved() {
  user="$(fnox -P proxy get WEBSHARE_PROXY_USERNAME 2>/dev/null || true)"
  pass="$(fnox -P proxy get WEBSHARE_PROXY_PASSWORD 2>/dev/null || true)"
  [ -n "$user" ] && [ -n "$pass" ] || { echo "No proxy saved yet: mise run local:proxy:setup"; exit 1; }
  url="$(proxy_url "$user" "$pass")"
}

to_github() {
  gh auth status >/dev/null 2>&1 || { echo "Sign in to GitHub first: gh auth login"; return 1; }
  local repo; repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
  show "gh secret set {WEBSHARE_PROXY_USERNAME,WEBSHARE_PROXY_PASSWORD,PROXY_URL} --repo $repo  (values from stdin)"
  printf '%s' "$user" | gh secret set WEBSHARE_PROXY_USERNAME --repo "$repo"
  printf '%s' "$pass" | gh secret set WEBSHARE_PROXY_PASSWORD --repo "$repo"
  printf '%s' "$url" | gh secret set PROXY_URL --repo "$repo"
  echo "✅ Saved as repository secrets of $repo (workflows read them as secrets.PROXY_URL ...)."
}

case "${1:-}" in
  --check)
    load_saved; test_proxy "$user" "$pass" && test_youtube "$user" "$pass" "$url"; exit $? ;;
  --github)
    load_saved; to_github; exit $? ;;
  "") ;;
  *) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac

cat <<EOF
On the Webshare dashboard, open "Proxy List" (it opens now) and set:
  Authentication Method: Username/Password   (IP Authorization cannot work: GitHub's address changes every run)
  Connection Method:     Rotating Proxy Endpoint   (Domain p.webshare.io, Port 80)
Then copy the Username and the Password shown there.
EOF
if command -v open >/dev/null; then show open "$DASHBOARD"; open "$DASHBOARD" || true; fi
printf 'Proxy username: '; IFS= read -r user
printf 'Proxy password (input hidden): '; IFS= read -rs pass; echo
user="$(printf '%s' "$user" | tr -d '[:space:]')"; user="${user%-rotate}"   # the -rotate suffix is added for you
pass="$(printf '%s' "$pass" | tr -d '[:space:]')"
[ -n "$user" ] && [ -n "$pass" ] || { echo "Both the username and the password are needed."; exit 1; }
url="$(proxy_url "$user" "$pass")"

test_proxy "$user" "$pass" || exit 1
youtube=0; test_youtube "$user" "$pass" "$url" || youtube=$?
save_local "$user" "$pass" "$url"
echo "✅ Saved as the local profile 'proxy'. Use it for one run:"
echo "     FNOX_PROFILE=proxy mise run local:transcripts:manage -- --method ytdlp download-missing --limit 5"
echo "   or switch it on: mise run local:profile:use -- ytdlp proxy   (off again: mise run local:profile:use -- ytdlp)"
[ "$youtube" = 0 ] || exit "$youtube"
printf 'Also save it as GitHub repository secrets, for a transcripts workflow? [y/N] '
read -r answer
case "$answer" in [yY]*) to_github ;; *) echo "Skipped. Later: mise run local:proxy:setup -- --github" ;; esac
