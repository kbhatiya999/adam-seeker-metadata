#!/usr/bin/env bash
# Docker lifecycle helper for act: tasks. Predictable and orphan-free.
#
#   docker.sh start             start Colima (preferred) or Docker Desktop and wait until ready
#   docker.sh stop              remove our containers/volumes, then stop Colima / quit Docker Desktop to free
#                               resources (only if no other containers are running)
#   docker.sh cleanup           remove our leftover containers/volumes (orphans) only
#   docker.sh run -- <command>  replace: clean old leftovers; ensure Docker is up (starting it
#                               if needed); run <command>; always clean up afterwards (even on
#                               Ctrl-C/failure) and stop Docker only if THIS run started it
set -u

LABEL="project=adam-seeker-metadata"
WAIT_SECS=120

# Runtime detection: Colima first, then Docker Desktop (macOS)
runtime() {
  if command -v colima >/dev/null 2>&1; then echo colima
  elif [ "$(uname -s)" = Darwin ] && [ -d /Applications/Docker.app ]; then echo desktop
  else echo none; fi
}

docker_up() { command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; }

start() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "❌ Docker is not installed. Run: mise run install"; return 1
  fi
  if docker_up; then echo "✅ Docker already running"; return 0; fi
  case "$(runtime)" in
    colima) echo "Starting Colima..."; colima start || { echo "❌ Could not start Colima"; return 1; } ;;
    desktop) echo "Starting Docker Desktop..."; open -a Docker || { echo "❌ Could not start Docker Desktop"; return 1; } ;;
    *) echo "❌ Docker is not running and no Colima/Docker Desktop found. Start your Docker daemon (e.g. 'sudo systemctl start docker')."; return 1 ;;
  esac
  for _ in $(seq "$WAIT_SECS"); do
    docker_up && { echo "✅ Docker is ready"; return 0; }
    sleep 1
  done
  echo "❌ Docker did not become ready within ${WAIT_SECS}s"; return 1
}

cleanup() {
  docker_up || return 0
  local containers volumes c
  containers="$(docker ps -aq --filter "label=$LABEL")"
  volumes=""
  for c in $containers; do
    volumes="$volumes $(docker inspect -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{end}}{{end}}' "$c")"
  done
  volumes="$volumes $(docker volume ls -q --filter 'name=act-Update-Video-List' --filter 'name=act-Rebuild-Video-List')"
  volumes="$(echo $volumes | tr ' ' '\n' | grep -v '^$' | sort -u | grep -v '^act-toolcache$')"
  if [ -n "$containers" ]; then echo "Removing leftover containers: $containers"; docker rm -f $containers >/dev/null; fi
  if [ -n "$volumes" ]; then echo "Removing leftover volumes: $(echo $volumes | tr '\n' ' ')"; docker volume rm -f $volumes >/dev/null; fi
  return 0
}

stop() {
  if ! docker_up; then echo "Docker is not running; nothing to stop"; return 0; fi
  cleanup
  local others
  others="$(docker ps -q | wc -l | tr -d ' ')"
  if [ "$others" != "0" ]; then
    echo "⚠️  $others other container(s) still running; leaving Docker running."
    return 0
  fi
  case "$(runtime)" in
    colima) echo "Stopping Colima..."; colima stop && echo "✅ Colima stopped" ;;
    desktop)
      echo "Quitting Docker Desktop..."
      osascript -e 'quit app "Docker"' >/dev/null 2>&1 || true
      for _ in $(seq 60); do docker_up || { echo "✅ Docker stopped"; return 0; }; sleep 1; done
      echo "⚠️  Docker still running after 60s" ;;
    *) echo "Stop Docker yourself (e.g. 'sudo systemctl stop docker')" ;;
  esac
}

run() {
  local started=0
  if ! docker_up; then start || return 1; started=1; fi
  cleanup   # replace: never reuse stale state from an earlier run
  trap 'trap - EXIT; cleanup; [ "'"$started"'" = 1 ] && stop; exit "${rc:-130}"' INT TERM
  "$@"; rc=$?
  trap - INT TERM
  cleanup
  [ "$started" = 1 ] && stop
  return "$rc"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  cleanup) cleanup ;;
  run) shift; [ "${1:-}" = "--" ] && shift; [ $# -gt 0 ] || { echo "usage: docker.sh run -- <command>"; exit 2; }; run "$@" ;;
  *) echo "usage: docker.sh {start|stop|cleanup|run -- <command>}"; exit 2 ;;
esac
