#!/usr/bin/env bash
# Run a command with the secrets and settings of the active fnox profile stack:
#   scripts/fx.sh <command ...>   =   fnox exec -P <active profiles> -- <command ...>
# The stack comes from FNOX_PROFILE, else the git-ignored .fnox-profile (see scripts/fnox_profile.py), plus the local
# `overrides` profile if you have one. With no profile it is plain `fnox exec`. Every mise task that needs secrets
# goes through this, so switching the profile (mise run local:profile:use, the menu, Tilt) changes all of them.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
stack="$(python3 "$here/fnox_profile.py" stack)"
if [ -n "$stack" ]; then
  exec fnox exec -P "$stack" -- "$@"
fi
exec fnox exec -- "$@"
