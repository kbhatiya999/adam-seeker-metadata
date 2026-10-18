#!/usr/bin/env bash
# Check that Docker is installed (needed for `act:` tasks); offer to install it if not.
# Docker is optional (local: and gh: tasks work without it), so this never fails `mise run install`.
set -u

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "✅ Docker is installed and running"
  else
    echo "⚠️  Docker is installed but not running. act: tasks start it themselves (or run: mise run docker:start)."
  fi
  exit 0
fi

echo "⚠️  Docker is not installed. It is only needed for act: tasks; local: and gh: tasks work without it."

case "$(uname -s)" in
  Darwin)
    if command -v brew >/dev/null 2>&1; then
      cmd="brew install --cask docker"
    else
      echo "Install Colima (https://github.com/abiosoft/colima) or Docker Desktop (https://docs.docker.com/desktop/setup/install/mac-install/)"
      exit 0
    fi
    ;;
  Linux)
    echo "Install Docker Engine: https://docs.docker.com/engine/install/ (needs sudo; not automated here)"
    exit 0
    ;;
  *)
    echo "Install Docker from https://docs.docker.com/get-docker/"
    exit 0
    ;;
esac

if [ ! -t 0 ]; then
  echo "Non-interactive shell; run: $cmd"
  exit 0
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
