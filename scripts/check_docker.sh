#!/usr/bin/env bash
# Check that Docker is installed (needed for `act:` tasks); offer to install it if not.
set -u

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "✅ Docker is installed and running"
  else
    echo "⚠️  Docker is installed but not running. Run `mise run docker:start` (Colima or Docker Desktop) before using act: tasks."
  fi
  exit 0
fi

echo "❌ Docker is not installed (required for act: tasks; local: and gh: tasks work without it)."

case "$(uname -s)" in
  Darwin)
    if command -v brew >/dev/null 2>&1; then
      cmd="brew install --cask docker"
    else
      echo "Install Docker Desktop from https://docs.docker.com/desktop/setup/install/mac-install/"
      exit 1
    fi
    ;;
  Linux)
    echo "Install Docker Engine: https://docs.docker.com/engine/install/ (needs sudo; not automated here)"
    exit 1
    ;;
  *)
    echo "Install Docker from https://docs.docker.com/get-docker/"
    exit 1
    ;;
esac

if [ ! -t 0 ]; then
  echo "Non-interactive shell; run: $cmd"
  exit 1
fi

read -r -p "Install Docker now with '$cmd'? [y/N] " answer
case "$answer" in
  [yY]|[yY][eE][sS])
    $cmd && echo "✅ Installed. Start Docker Desktop once, then re-run: mise run install"
    ;;
  *)
    echo "Skipped. Install later with: $cmd"
    ;;
esac
