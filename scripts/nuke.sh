#!/usr/bin/env bash
# Opposite of `mise run install`: remove what this project created.
#
# Default (project-scoped):
#   .venv, .act/ (act action/cache/artifact dirs), __pycache__,
#   Docker containers labelled project=adam-seeker-metadata and the volumes they mount,
#   Docker volumes named after our workflows, and the act runner image from .actrc.
# --all (also shared/global things, may affect other projects):
#   uv cache, act-toolcache volume, mise installs of the tools in mise.toml,
#   fnox.local.toml (your local secrets).
# Flags: --all  --yes (skip prompt)  --dry-run (only print)
# Docker itself is never uninstalled.
set -u

LABEL="project=adam-seeker-metadata"
IMAGE="$(sed -n 's/^-P ubuntu-latest=//p' .actrc 2>/dev/null)"
ALL=0 YES=0 DRY=0
for a in "$@"; do
  case "$a" in
    --all) ALL=1 ;; --yes|-y) YES=1 ;; --dry-run) DRY=1 ;;
    *) echo "Unknown flag: $a (use --all, --yes, --dry-run)"; exit 2 ;;
  esac
done

run() { if [ "$DRY" = 1 ]; then echo "  [dry-run] $*"; else echo "  $*"; "$@"; fi; }

docker_ok=0
command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && docker_ok=1

containers="" volumes=""
if [ "$docker_ok" = 1 ]; then
  containers="$(docker ps -aq --filter "label=$LABEL")"
  for c in $containers; do
    volumes="$volumes $(docker inspect -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{end}}{{end}}' "$c")"
  done
  volumes="$volumes $(docker volume ls -q --filter 'name=act-Update-Video-List' --filter 'name=act-Rebuild-Video-List')"
  volumes="$(echo $volumes | tr ' ' '\n' | grep -v '^$' | sort -u | grep -v '^act-toolcache$')"
fi

echo "This will remove:"
echo "  - .venv, .act/, .vars, dist/, scripts/__pycache__"
if [ "$docker_ok" = 1 ]; then
  echo "  - Docker containers ($LABEL): ${containers:-none}"
  echo "  - Docker volumes: $(echo $volumes | tr '\n' ' ')"; [ -z "$volumes" ] && echo "    (none)"
  [ -n "$IMAGE" ] && echo "  - Docker image: $IMAGE"
else
  echo "  - (Docker not installed or not running: Docker cleanup SKIPPED)"
fi
if [ "$ALL" = 1 ]; then
  echo "  - uv cache (global, shared by all uv projects)"
  echo "  - Docker volume act-toolcache (shared by all act projects)"
  echo "  - mise installs of this project's exact tool versions (python, uv, act, fnox, gh)"
  echo "  - fnox.local.toml (local secrets)"
fi

if [ "$DRY" = 0 ] && [ "$YES" = 0 ]; then
  if [ ! -t 0 ]; then echo "Non-interactive: pass --yes to proceed."; exit 1; fi
  read -r -p "Proceed? [y/N] " ans
  case "$ans" in [yY]|[yY][eE][sS]) ;; *) echo "Aborted."; exit 1 ;; esac
fi

mise_tools=""
if [ "$ALL" = 1 ]; then
  # Only the exact versions this project resolves to, not every installed version
  mise_tools="$(mise ls --current --json 2>/dev/null | MISE_FILE="$PWD/mise.toml" python3 -c '
import json, os, sys
for name, versions in json.load(sys.stdin).items():
    for v in versions:
        if v.get("installed") and v.get("source", {}).get("path") == os.environ["MISE_FILE"]:
            print(name + "@" + v["version"])
' 2>/dev/null)"
fi

echo "Nuking..."
run rm -rf .venv .act .vars dist scripts/__pycache__
if [ "$docker_ok" = 1 ]; then
  [ -n "$containers" ] && run docker rm -f $containers
  [ -n "$volumes" ] && run docker volume rm -f $volumes
  [ -n "$IMAGE" ] && docker image inspect "$IMAGE" >/dev/null 2>&1 && run docker image rm -f "$IMAGE"
fi
if [ "$ALL" = 1 ]; then
  command -v uv >/dev/null 2>&1 && run uv cache clean
  [ "$docker_ok" = 1 ] && run docker volume rm -f act-toolcache
  run rm -f fnox.local.toml
  # Uninstall last: this script may be running under these tools.
  [ -n "$mise_tools" ] && run mise uninstall $mise_tools
fi
echo "Done. Rebuild with: mise install && mise run install"
