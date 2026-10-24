#!/usr/bin/env bash
# Download a few transcripts the SAME way in three places:
#   transcripts_run.sh local|act|gh [NETWORK] [METHOD] [LIMIT]
#     NETWORK  direct | proxy | cookies | proxy+cookies   (default proxy)
#     METHOD   ytdlp | youtube_transcript_api            (default ytdlp)
#     LIMIT    stop after this many transcripts          (default 3)
#   local  runs it on this computer, act in Docker (the workflow, nothing published), gh on GitHub (the real workflow).
# The network settings are ENVIRONMENT VARIABLES with the same names everywhere:
#   proxy    PROXY_URL, WEBSHARE_PROXY_USERNAME, WEBSHARE_PROXY_PASSWORD   (mise run local:proxy:setup)
#   cookies  YTDLP_COOKIES_BASE64 (the cookies.txt as one base64 line)     (mise run local:cookies:setup)
# local and act take them from the fnox profiles `proxy` and `cookies` (whatever profile stack is active); GitHub takes
# the repository secrets of the same names (`-- --github` on both setup tasks). Values never appear on a command line.
set -euo pipefail
cd "$(dirname "$0")/.."
where="${1:-}"; network="${2:-proxy}"; method="${3:-ytdlp}"; limit="${4:-3}"
case "$where" in local|act|gh) ;; *) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;; esac
case "$network" in direct|proxy|cookies|proxy+cookies) ;; *) echo "NETWORK must be direct, proxy, cookies or proxy+cookies"; exit 2 ;; esac
case "$method" in ytdlp|youtube_transcript_api) ;; *) echo "METHOD must be ytdlp or youtube_transcript_api"; exit 2 ;; esac
[[ "$limit" =~ ^[0-9]+$ ]] || { echo "LIMIT must be a number"; exit 2; }

names=()    # the variables this network needs
profiles=() # the local fnox profiles that hold them
if [[ "$network" == *proxy* ]]; then names+=(PROXY_URL WEBSHARE_PROXY_USERNAME WEBSHARE_PROXY_PASSWORD); profiles+=(proxy); fi
if [[ "$network" == *cookies* ]]; then names+=(YTDLP_COOKIES_BASE64); profiles+=(cookies); fi
profile_list="$(IFS=,; echo "${profiles[*]:-}")"
setup_hint() { case "$1" in PROXY_URL|WEBSHARE_*) echo "mise run local:proxy:setup";; *) echo "mise run local:cookies:setup";; esac; }

need_local() { # every variable must be saved in its local profile
  local n p
  for n in "${names[@]}"; do
    case "$n" in YTDLP_COOKIES_BASE64) p=cookies;; *) p=proxy;; esac
    [ -n "$(fnox -P "$p" get "$n" 2>/dev/null || true)" ] || { echo "$n is not saved yet: $(setup_hint "$n")"; exit 1; }
  done
}
unset_args=() # variables of the networks NOT chosen must not leak in from your shell
for n in PROXY_URL WEBSHARE_PROXY_USERNAME WEBSHARE_PROXY_PASSWORD YTDLP_COOKIES_BASE64; do
  [[ " ${names[*]:-} " == *" $n "* ]] || unset_args+=(-u "$n")
done

case "$where" in
  local)
    [ ${#names[@]} -eq 0 ] || need_local
    run=(env "${unset_args[@]}" uv run --no-sync seeker transcripts --method "$method" download-missing --limit "$limit")
    echo "local: network=$network method=$method limit=$limit"
    if [ -n "$profile_list" ]; then exec fnox exec -P "$profile_list" -- "${run[@]}"; fi
    exec "${run[@]}" ;;
  act)
    [ ${#names[@]} -eq 0 ] || need_local
    args=(workflow_dispatch -W .github/workflows/download-transcripts.yml
          --input "network=$network" --input "method=$method" --input "limit=$limit")
    for n in "${names[@]:-}"; do [ -z "$n" ] || args+=(-s "$n"); done   # -s NAME takes the value from the environment
    echo "act: network=$network method=$method limit=$limit"
    if [ -n "$profile_list" ]; then exec fnox exec -P "$profile_list" -- act "${args[@]}"; fi
    exec act "${args[@]}" ;;
  gh)
    have="$(gh secret list --json name -q '.[].name')"
    for n in "${names[@]:-}"; do
      [ -z "$n" ] || grep -qx "$n" <<<"$have" || { echo "The GitHub secret $n is not set: $(setup_hint "$n") -- --github"; exit 1; }
    done
    ref="${REF:-$(git branch --show-current)}"
    latest() { gh run list --workflow download-transcripts.yml --limit 1 --json databaseId -q '.[0].databaseId // 0'; }
    before="$(latest)"
    gh workflow run download-transcripts.yml --ref "$ref" -f network="$network" -f method="$method" -f limit="$limit"
    echo "gh: started on $ref: network=$network method=$method limit=$limit. Waiting for the run to appear ..."
    id="$before"
    for _ in $(seq 1 30); do sleep 2; id="$(latest)"; [ "$id" != "$before" ] && break; done
    [ "$id" != "$before" ] || { echo "The run did not appear. Check: mise run gh:list"; exit 1; }
    gh run watch --exit-status "$id" || status=$?
    echo "Run: $(gh run view "$id" --json url -q .url)"
    exit "${status:-0}" ;;
esac
