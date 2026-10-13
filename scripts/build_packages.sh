#!/usr/bin/env bash
# Build the workspace packages as separate wheels and verify them in clean virtualenvs.
#
#   build_packages.sh sdks [--sdist] [--no-verify]   -> dist/sdks/seeker_sdk_<name>-<version>-py3-none-any.whl
#   build_packages.sh apps [--sdist] [--no-verify]   -> dist/apps/seeker_<app>-<version>-py3-none-any.whl
#
# Every wheel must start with "seeker" (distribution names seeker-sdk-* and seeker-*). Verification
# installs the wheels (not the workspace) into a throwaway venv, checks that each SDK installs and
# imports on its own, and that the plugins are discovered through entry points.
set -eu
cd "$(dirname "$0")/.."

kind="${1:-}"; shift || true
case "$kind" in sdks|apps) ;; *) echo "usage: $0 <sdks|apps> [--sdist] [--no-verify]"; exit 2 ;; esac
sdist=0; verify=1
for a in "$@"; do
  case "$a" in --sdist) sdist=1 ;; --no-verify) verify=0 ;; *) echo "unknown option $a"; exit 2 ;; esac
done

out="dist/$kind"
rm -rf "$out"; mkdir -p "$out"

build_flags=(--wheel); [ "$sdist" = 1 ] && build_flags+=(--sdist)
count=0
for dir in "$kind"/*/; do
  [ -f "$dir/pyproject.toml" ] || continue
  name="$(sed -n 's/^name = "\(.*\)"/\1/p' "$dir/pyproject.toml" | head -1)"
  echo "▶ building $name"
  uv build --package "$name" "${build_flags[@]}" --out-dir "$out" >/dev/null
  count=$((count + 1))
done
[ "$count" -gt 0 ] || { echo "no packages found in $kind/"; exit 1; }

echo; echo "Built wheels in $out:"
bad=0
for w in "$out"/*.whl; do
  base="$(basename "$w")"
  case "$base" in seeker*) printf '  ✅ %s (%s KB)\n' "$base" "$(( $(wc -c < "$w") / 1024 ))" ;; *) echo "  ❌ $base does not start with 'seeker'"; bad=1 ;; esac
done
[ "$bad" = 0 ] || exit 1
[ "$verify" = 1 ] || exit 0

echo; echo "Verifying in clean virtualenvs (installing the wheels, not the workspace)..."
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
links=(--find-links "$out"); [ -d dist/sdks ] && links+=(--find-links dist/sdks)

install_into() { # venv-dir packages...
  local venv="$1"; shift
  uv venv --quiet "$venv" && uv pip install --quiet --python "$venv/bin/python" "${links[@]}" "$@"
}

if [ "$kind" = sdks ]; then
  # 1. core alone: no third-party dependencies at all
  install_into "$tmp/core" seeker-sdk-core
  "$tmp/core/bin/python" - <<'PY'
import importlib.metadata as m, seeker_sdk_core
deps = m.requires("seeker-sdk-core") or []
assert not deps, f"seeker-sdk-core must have no dependencies, has {deps}"
print("  ✅ seeker-sdk-core installs alone (no third-party dependencies)")
PY
  # 2. each other SDK alone (its own dependencies + core), and its plugins are discovered
  for dir in sdks/*/; do
    name="$(sed -n 's/^name = "\(.*\)"/\1/p' "$dir/pyproject.toml" | head -1)"
    [ "$name" = seeker-sdk-core ] && continue
    install_into "$tmp/$name" "$name"
    "$tmp/$name/bin/python" - "$name" <<'PY'
import importlib, importlib.metadata as m, sys
name = sys.argv[1]
module = importlib.import_module(name.replace("-", "_"))
groups = sorted({ep.group for ep in m.entry_points() if ep.dist and ep.dist.name == name})
from seeker_sdk_core import plugins
found = {g: plugins.names(g) for g in groups}
print(f"  ✅ {name} {module.__version__} installs alone; plugin groups: {found or 'none'}")
PY
  done
else
  install_into "$tmp/apps" $(for dir in apps/*/; do sed -n 's/^name = "\(.*\)"/\1/p' "$dir/pyproject.toml" | head -1; done)
  "$tmp/apps/bin/seeker" plugins >/dev/null && echo "  ✅ seeker (CLI) runs from the installed wheels and finds the plugins"
  [ -x "$tmp/apps/bin/seeker-tui" ] && echo "  ✅ seeker-tui entry point installed"
fi
echo; echo "Done."
