#!/usr/bin/env bash
# Workflow step: check the runner can decrypt the secrets it needs, then hide their values from the logs.
#   ci_unlock.sh               every encrypted secret in fnox.toml must decrypt (a wrong key fails here, not later)
#   ci_unlock.sh NAME ...      these secrets must be set and decrypt (read under FNOX_PROFILE, if set)
# The secrets are encrypted (age) in fnox.toml; FNOX_AGE_KEY (the repository secret, the `ci` recipient) unlocks them.
# fnox gives an EMPTY value, not an error, when the key is missing or wrong (tested with fnox 1.39), so this step
# makes that loud. GitHub masks only secrets it knows (FNOX_AGE_KEY), not the decrypted values: `fnox ci-redact`
# prints ::add-mask:: for each of them. Without FNOX_AGE_KEY (a fork that uses plain repository secrets instead) it
# only warns, unless NAMEs were asked for.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${FNOX_AGE_KEY:-}" ]; then
  if [ $# -gt 0 ]; then
    echo "::error::The repository secret FNOX_AGE_KEY is not set, so $* cannot be decrypted. Run: mise run local:secrets:ci-key"
    exit 1
  fi
  echo "::warning::No FNOX_AGE_KEY secret: running without the encrypted secrets in fnox.toml (plain repository secrets still work)."
  exit 0
fi
if [ $# -eq 0 ]; then
  python3 scripts/secrets.py check || {
    echo "::error::FNOX_AGE_KEY cannot decrypt the secrets in fnox.toml: it is not a recipient. Run: mise run local:secrets:ci-key"
    exit 1
  }
fi
for name in "$@"; do
  fnox get "$name" >/dev/null 2>&1 || {
    echo "::error::Cannot decrypt $name${FNOX_PROFILE:+ (profile $FNOX_PROFILE)}: it is not saved in fnox.toml, or FNOX_AGE_KEY is not a recipient. Run: mise run local:secrets:check, then local:secrets:ci-key"
    exit 1
  }
done
fnox ci-redact
echo "Secrets unlocked${FNOX_PROFILE:+ for profile $FNOX_PROFILE}: ${*:-all that can be decrypted}; their values are masked in the logs."
