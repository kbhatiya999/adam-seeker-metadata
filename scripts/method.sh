#!/usr/bin/env bash
# Switch / show the method settings for one place a job can run.
#
#   method.sh <local|act|gh> set  <master-list|transcript> <value|unset>
#   method.sh <local|act|gh> show [master-list|transcript]
#
# Settings:
#   master-list -> MASTER_LIST_METHOD   youtube_api | ytdlp      (how new videos are discovered)
#   transcript  -> TRANSCRIPT_METHOD    ytdlp | youtube_transcript_api   (how transcripts are fetched)
# Where each target stores it:
#   local -> fnox.local.toml   (git-ignored; read by `mise run local:*` through fnox)
#   act   -> .vars             (git-ignored; read by act as ${{ vars.NAME }})
#   gh    -> repository variable (gh variable set/delete/list; read by the workflows as vars.NAME)
# "unset" removes the setting. Unset master-list = the old implicit behaviour (API if a key is
# present, else yt-dlp). Unset transcript = the transcript script refuses to run until chosen.
set -u

target="${1:-}"; action="${2:-}"; setting="${3:-}"; value="${4:-}"
usage() { sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
[ -n "$target" ] && [ -n "$action" ] || usage

name_of() { case "$1" in master-list) echo MASTER_LIST_METHOD ;; transcript) echo TRANSCRIPT_METHOD ;; *) return 1 ;; esac; }
allowed_of() { case "$1" in master-list) echo "youtube_api ytdlp" ;; transcript) echo "ytdlp youtube_transcript_api" ;; esac; }
show_cmd() { printf '  \033[2m$ %s\033[0m\n' "$*" >&2; }

LOCAL_FILE="fnox.local.toml"; ACT_FILE=".vars"

read_value() { # target NAME -> value or empty
  case "$1" in
    local) [ -f "$LOCAL_FILE" ] && sed -n "s/^$2 *= *{ *default *= *\"\(.*\)\" *}.*/\1/p" "$LOCAL_FILE" | head -1 ;;
    act)   [ -f "$ACT_FILE" ] && sed -n "s/^$2=//p" "$ACT_FILE" | head -1 ;;
    gh)    gh variable list --json name,value -q ".[] | select(.name==\"$2\") | .value" 2>/dev/null ;;
  esac
}

write_value() { # target NAME value|unset
  local t="$1" n="$2" v="$3"
  case "$t" in
    local)
      show_cmd "edit $LOCAL_FILE: $([ "$v" = unset ] && echo "remove $n" || echo "$n = { default = \"$v\" }") under [secrets]"
      V="$v" N="$n" python3 - "$LOCAL_FILE" <<'PY'
import os, re, sys
path, n, v = sys.argv[1], os.environ["N"], os.environ["V"]
text = open(path).read() if os.path.exists(path) else ""
text = re.sub(rf'^{n}\s*=.*\n?', '', text, flags=re.M)
if v != "unset":
    if "[secrets]" not in text:
        text += ("\n" if text and not text.endswith("\n") else "") + "[secrets]\n"
    text = text.replace("[secrets]\n", f'[secrets]\n{n} = {{ default = "{v}" }}\n', 1)
open(path, "w").write(text)
PY
      ;;
    act)
      show_cmd "edit $ACT_FILE: $([ "$v" = unset ] && echo "remove $n" || echo "$n=$v")"
      touch "$ACT_FILE"; grep -v "^$n=" "$ACT_FILE" > "$ACT_FILE.tmp"; mv "$ACT_FILE.tmp" "$ACT_FILE"
      [ "$v" = unset ] || echo "$n=$v" >> "$ACT_FILE"
      ;;
    gh)
      if [ "$v" = unset ]; then
        show_cmd gh variable delete "$n"; gh variable delete "$n"
      else
        show_cmd gh variable set "$n" --body "$v"; gh variable set "$n" --body "$v"
      fi
      ;;
  esac
}

case "$target" in local|act|gh) ;; *) usage ;; esac

case "$action" in
  set)
    n="$(name_of "$setting")" || usage
    [ -n "$value" ] || usage
    if [ "$value" != unset ]; then
      case " $(allowed_of "$setting") " in *" $value "*) ;; *) echo "$setting must be one of: $(allowed_of "$setting") (or unset)"; exit 2 ;; esac
    fi
    write_value "$target" "$n" "$value" || exit 1
    echo "✅ $target: $n = ${value}"
    [ "$target" = gh ] && [ "$setting" = transcript ] && echo "ℹ️  No GitHub workflow uses TRANSCRIPT_METHOD yet; it is stored for when one does."
    exit 0 ;;
  show)
    for s in ${setting:-master-list transcript}; do
      n="$(name_of "$s")" || usage
      v="$(read_value "$target" "$n")"
      printf '%-12s %-18s %s\n' "$target" "$n" "${v:-(unset)}"
    done
    exit 0 ;;
  *) usage ;;
esac
