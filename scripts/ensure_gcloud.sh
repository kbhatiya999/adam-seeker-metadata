#!/usr/bin/env bash
# Make sure the mise-managed gcloud is installed and works. gcloud's installer needs Python 3.10+,
# which the macOS system Python is not, so point it at mise's Python (also set via CLOUDSDK_PYTHON in mise.toml).
set -u
if gcloud --version >/dev/null 2>&1; then echo "✅ gcloud $(gcloud --version 2>/dev/null | head -1)"; exit 0; fi
py="$(mise which python 2>/dev/null)"
[ -n "$py" ] || { echo "❌ mise python not found; run: mise install"; exit 1; }
echo "Installing gcloud via mise..."
CLOUDSDK_PYTHON="$py" mise install gcloud || { echo "❌ gcloud install failed"; exit 1; }
gcloud --version >/dev/null 2>&1 && echo "✅ gcloud installed" || { echo "❌ gcloud still not usable"; exit 1; }
