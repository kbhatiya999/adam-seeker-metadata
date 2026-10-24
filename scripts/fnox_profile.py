#!/usr/bin/env python3
"""fnox profiles for this repo: which profile stack is active, what each profile sets, switching.

    fnox_profile.py stack            the stack to give fnox (-P): the active profiles, then `overrides` if you have it
    fnox_profile.py get KEY          the effective value of a SETTING under that stack (empty if unset)
    fnox_profile.py show             active stack, effective settings, which secrets are set (never their values)
    fnox_profile.py list [--json]    the profiles and the settings each one sets
    fnox_profile.py use [NAME ...]   make NAME ... the active stack (later ones win); no names = the default profile

Secrets (API keys) sit at the top of fnox.local.toml and every profile inherits them. Settings (methods, model
provider, model) live only in profiles: the committed ones in fnox.toml, and your own in the local `overrides`
profile (`mise run local:method:set` writes it), which is always applied last. The active stack is kept in the
git-ignored .fnox-profile; FNOX_PROFILE in the environment wins over it. Standard library only (Python 3.11+).
"""

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
ACTIVE = ROOT / ".fnox-profile"
FILES = (ROOT / "fnox.toml", ROOT / "fnox.local.toml")   # later files win, as in fnox
OVERRIDES = "overrides"
SETTINGS = ("MASTER_LIST_METHOD", "TRANSCRIPT_METHOD", "TRANSCRIPT_FORMAT", "TRANSCRIPT_FINAL",
            "SEEKER_LLM_PROVIDER", "SEEKER_GEMINI_MODEL", "SEEKER_GEMINI_RPM")
# The one kind of profile that holds secrets: the local `proxy` (mise run local:proxy:setup), so the proxy is used
# only when picked and your own runs go direct.
NETWORK = ("PROXY_URL", "WEBSHARE_PROXY_USERNAME", "WEBSHARE_PROXY_PASSWORD", "YTDLP_COOKIES_BASE64")


def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def profiles() -> Dict[str, Dict[str, str]]:
    """name -> {KEY: value} for what each profile sets (settings show their value, anything else "(secret)")."""
    out: Dict[str, Dict[str, str]] = {}
    for path in FILES:
        for name, body in _load(path).get("profiles", {}).items():
            for key, spec in (body.get("secrets") or {}).items():
                value = spec.get("default", "(secret)") if isinstance(spec, dict) else "(secret)"
                out.setdefault(name, {})[key] = value if key in SETTINGS else "(secret)"
    return out


def declared() -> List[str]:
    """Every name fnox knows: the top-level secrets of both files and every profile key."""
    names = set()
    for path in FILES:
        data = _load(path)
        names.update((data.get("secrets") or {}).keys())
        for body in data.get("profiles", {}).values():
            names.update((body.get("secrets") or {}).keys())
    return sorted(names)


def kind(sets: Dict[str, str]) -> str:
    if "SEEKER_LLM_PROVIDER" in sets or "SEEKER_GEMINI_MODEL" in sets:
        return "model"
    if any(k.endswith("_METHOD") for k in sets):
        return "methods"
    if any(k in NETWORK for k in sets):
        return "network"
    return "other"


def _split(text: str) -> List[str]:
    return [p for p in re.split(r"[\s,]+", text.strip()) if p and p not in ("default", "none")]


def active() -> List[str]:
    """The chosen profiles (FNOX_PROFILE, else .fnox-profile); names fnox does not know are dropped with a warning."""
    raw = os.environ.get("FNOX_PROFILE")
    chosen = _split(raw) if raw is not None else (_split(ACTIVE.read_text()) if ACTIVE.exists() else [])
    known = profiles()
    for name in chosen:
        if name not in known:
            print(f"fnox_profile: ignoring unknown profile {name!r} (see: mise run local:profile:show)", file=sys.stderr)
    return [n for n in chosen if n in known and n != OVERRIDES]


def stack() -> List[str]:
    return active() + ([OVERRIDES] if OVERRIDES in profiles() else [])


def effective(key: str, names: List[str]) -> str:
    """What fnox gives KEY under the stack (empty if unset). Used for settings and to tell if a secret is set."""
    command = ["fnox"] + (["-P", ",".join(names)] if names else []) + ["get", key]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def cmd_show() -> int:
    names = stack()
    chosen = active()
    print("Active profile stack:", ", ".join(names) if names else "default (no profile)")
    if chosen != names:
        print(f"  ({OVERRIDES!r} is your local profile, always applied last)")
    keys = declared()
    print("Settings:")
    for key in SETTINGS:
        if key in keys:
            print(f"  {key:<22} {effective(key, names) or '(unset)'}")
    print("Secrets (values never shown):")
    for key in keys:
        if key not in SETTINGS:
            print(f"  {key:<22} {'set' if effective(key, names) else 'not set'}")
    print("Profiles (pick one methods and one model profile, plus `proxy` if you set one up with "
          "mise run local:proxy:setup; e.g. mise run local:profile:use -- ytdlp gemini-lite):")
    for name, sets in sorted(profiles().items()):
        mark = "*" if name in names else " "
        print(f"  {mark} {name:<14} {kind(sets):<8} " + ", ".join(f"{k}={v}" for k, v in sets.items()))
    return 0


def cmd_list(as_json: bool) -> int:
    found = {name: {"kind": kind(sets), "sets": sets} for name, sets in sorted(profiles().items())}
    if as_json:
        print(json.dumps({"active": active(), "profiles": found}))
    else:
        for name, info in found.items():
            print(f"{name:<14} {info['kind']:<8} " + ", ".join(f"{k}={v}" for k, v in info["sets"].items()))
    return 0


def cmd_use(names: List[str]) -> int:
    names = [n for n in names if n not in ("default", "none", "")]
    known = profiles()
    unknown = [n for n in names if n not in known]
    if unknown:
        print(f"Unknown profile(s): {', '.join(unknown)}. Known: {', '.join(sorted(known))}", file=sys.stderr)
        return 2
    if OVERRIDES in names:
        print(f"{OVERRIDES!r} is always applied last on its own; leave it out.", file=sys.stderr)
        return 2
    if names:
        ACTIVE.write_text(",".join(names) + "\n")
    elif ACTIVE.exists():
        ACTIVE.unlink()
    print("Active profile stack:", ", ".join(stack()) or "default (no profile)")
    print("Every mise task uses it from now on (terminal, menu, Tilt).")
    return 0


def main(argv: List[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    command, rest = argv[0], argv[1:]
    if command == "stack":
        print(",".join(stack()))
        return 0
    if command == "get" and len(rest) == 1:
        print(effective(rest[0], stack()))
        return 0
    if command == "show":
        return cmd_show()
    if command == "list":
        return cmd_list("--json" in rest)
    if command == "use":
        return cmd_use(rest)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
