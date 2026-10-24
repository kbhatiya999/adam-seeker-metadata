#!/usr/bin/env python3
"""Encrypted secrets: the values live in the committed fnox.toml, encrypted with age, readable by two keys.

    secrets.py check               can this machine decrypt? which secrets are set (never their values)
    secrets.py init                use (or make) your personal age key and make it a recipient in fnox.toml
    secrets.py set NAME [PROFILE]  encrypt the value from stdin into fnox.toml (top level, or that profile)
    secrets.py ci-key              make a NEW CI key: GitHub secret FNOX_AGE_KEY, recipient, re-encrypt everything
    secrets.py reencrypt           re-encrypt every secret for the current recipients (all profiles)
    secrets.py migrate             move the secrets still in fnox.local.toml into fnox.toml, encrypted
    secrets.py publish [--yes]     commit fnox.toml and push it to main (secret changes go straight to main)
    secrets.py with-key CMD ...    run CMD with FNOX_AGE_KEY set from your personal key (act passes it on)

Two recipients (tested with fnox 1.39):
  personal  ~/.config/fnox/age.txt (fnox's default place; keep a copy in your password manager). It decrypts
            on this computer and in act.
  ci        exists only as the GitHub secret FNOX_AGE_KEY. Losing it costs nothing: `ci-key` makes a new one,
            because the personal key can re-encrypt everything.
The code only ever sees environment variables (YOUTUBE_API_KEY, PROXY_URL ...), so moving to another store later
(e.g. Bitwarden Secrets Manager) means changing fnox.toml entries, not code. Values are never printed; they go to
fnox through stdin. Standard library only.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "fnox.toml"
LOCAL = ROOT / "fnox.local.toml"
PROVIDER = "age"
GH_SECRET = "FNOX_AGE_KEY"
KEY_DIR = Path(os.environ.get("FNOX_CONFIG_DIR") or Path.home() / ".config" / "fnox")
PERSONAL_KEY = Path(os.environ.get("FNOX_AGE_KEY_FILE") or KEY_DIR / "age.txt")
LABELS = ("personal", "ci")
# settings stay readable in fnox.toml; everything else declared there is a secret
SETTINGS = ("MASTER_LIST_METHOD", "TRANSCRIPT_METHOD", "TRANSCRIPT_FORMAT", "TRANSCRIPT_FINAL",
            "SEEKER_LLM_PROVIDER", "SEEKER_GEMINI_MODEL", "SEEKER_GEMINI_RPM")
PUBLIC = re.compile(r"age1[0-9a-z]{58}")


def say(text: str = "") -> None:
    print(text, flush=True)


def shown(cmd: str) -> None:
    print(f"  \033[2m$ {cmd}\033[0m", file=sys.stderr, flush=True)


def run(cmd: List[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kw)


# ---- fnox.toml: the recipients block ---------------------------------------------------------------------------

BLOCK = re.compile(r'^\[providers\.age\]\n(?:(?!\[).*\n?)*', re.M)


def provider_block(recipients: Dict[str, str]) -> str:
    lines = ["[providers.age]", 'type = "age"',
             "# Two keys can read the secrets below: `personal` (~/.config/fnox/age.txt, also used by act) and `ci`",
             "# (only in the GitHub secret FNOX_AGE_KEY). Change them with: mise run local:secrets:init / ci-key",
             "recipients = ["]
    lines += [f'  "{key}", # {label}' for label, key in recipients.items()]
    return "\n".join(lines + ["]", ""]) + "\n"


def recipients(text: str) -> Dict[str, str]:
    """label -> public key, from the commented recipients list."""
    m = BLOCK.search(text)
    found: Dict[str, str] = {}
    for line in (m.group(0) if m else "").splitlines():
        key, label = PUBLIC.search(line), re.search(r"#\s*(\w+)", line)
        if key and label:
            found[label.group(1)] = key.group(0)
    return found


def with_recipient(text: str, label: str, key: str) -> str:
    """fnox.toml text with LABEL's recipient set to KEY (the block is added before the first [secrets...] if new)."""
    current = recipients(text)
    current[label] = key
    ordered = {k: current[k] for k in LABELS if k in current} | {k: v for k, v in current.items() if k not in LABELS}
    block = provider_block(ordered)
    if BLOCK.search(text):
        return BLOCK.sub(lambda _: block, text, count=1)
    at = text.find("\n[secrets.")
    at = at + 1 if at >= 0 else len(text)
    return text[:at] + block + "\n" + text[at:]


# ---- what is encrypted where -----------------------------------------------------------------------------------

def encrypted(text: str) -> List[Tuple[str, Optional[str]]]:
    """(name, profile or None) for every secret stored with the age provider."""
    data = tomllib.loads(text)
    out = [(n, None) for n, spec in (data.get("secrets") or {}).items()
           if isinstance(spec, dict) and spec.get("provider") == PROVIDER]
    for profile, body in (data.get("profiles") or {}).items():
        out += [(n, profile) for n, spec in ((body or {}).get("secrets") or {}).items()
                if isinstance(spec, dict) and spec.get("provider") == PROVIDER]
    return out


def local_secrets(text: str) -> List[Tuple[str, Optional[str], str]]:
    """(name, profile or None, value) of plain secret values in fnox.local.toml (settings are left alone)."""
    data = tomllib.loads(text)
    out = [(n, None, s["default"]) for n, s in (data.get("secrets") or {}).items()
           if isinstance(s, dict) and "default" in s and n not in SETTINGS]
    for profile, body in (data.get("profiles") or {}).items():
        out += [(n, profile, s["default"]) for n, s in ((body or {}).get("secrets") or {}).items()
                if isinstance(s, dict) and "default" in s and n not in SETTINGS]
    return out


def without_local(text: str, gone: List[Tuple[str, Optional[str]]]) -> str:
    """fnox.local.toml text without the given secret lines; sections left empty are dropped with their comment."""
    lines, section, keep = text.splitlines(), None, []
    names = {(n, p) for n, p in gone}
    for line in lines:
        head = re.match(r"^\[(.+)\]\s*$", line)
        if head:
            section = head.group(1)
        m = re.match(r"^([A-Z0-9_]+)\s*=", line)
        profile = None if section == "secrets" else (section[len("profiles."):-len(".secrets")]
                                                     if section and section.endswith(".secrets") else "?")
        if m and (m.group(1), profile) in names:
            continue
        keep.append(line)
    out, i = [], 0
    while i < len(keep):          # drop headers whose section is now empty (and the comment lines right above)
        head = re.match(r"^\[(.+)\]\s*$", keep[i])
        if head:
            j = i + 1
            while j < len(keep) and not keep[j].strip():
                j += 1
            if j == len(keep) or keep[j].startswith("["):
                while out and out[-1].startswith("#"):
                    out.pop()
                i = j
                continue
        out.append(keep[i])
        i += 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip("\n") + "\n" if any(x.strip() for x in out) else ""


# ---- commands --------------------------------------------------------------------------------------------------

def public_key(private_file: Path) -> str:
    m = PUBLIC.search(private_file.read_text())
    if not m:
        raise SystemExit(f"{private_file} has no age public key line (# public key: age1...)")
    return m.group(0)


def keygen() -> str:
    """A new age identity file's text (private key + public key comment), from age-keygen (a mise tool)."""
    exe = shutil.which("age-keygen")
    cmd = [exe] if exe else ["mise", "exec", "age", "--", "age-keygen"]
    r = run(cmd)
    if r.returncode != 0 or "AGE-SECRET-KEY-" not in r.stdout:
        raise SystemExit("age-keygen failed (it is a mise tool: mise install)")
    return r.stdout


def plain_in_config(name: str, profile: Optional[str]) -> bool:
    return any(n == name and p == profile for n, p, _ in local_secrets(CONFIG.read_text()))


def fnox_set(name: str, profile: Optional[str], value: str) -> bool:
    """Encrypt VALUE into fnox.toml. fnox copies an entry that also exists in fnox.local.toml INCLUDING its plain
    `default` value (tested with fnox 1.39), so a local copy must be gone first; the result is checked anyway."""
    where = f" (profile {profile})" if profile else ""
    if LOCAL.exists() and any(n == name and p == profile for n, p, _ in local_secrets(LOCAL.read_text())):
        say(f"❌ {name}{where} is still in fnox.local.toml: fnox would copy that plain value into fnox.toml. "
            "Move it with: mise run local:secrets:migrate")
        return False
    cmd = ["fnox", "set", name, "-p", PROVIDER] + (["-P", profile] if profile else [])
    shown(" ".join(cmd) + "   (value from stdin)")
    r = run(cmd, input=value)
    if r.returncode != 0:
        say(f"❌ fnox set {name} failed: {r.stderr.strip()[:300]}")
        return False
    if plain_in_config(name, profile):
        say(f"❌ fnox.toml now holds a PLAIN value for {name}{where}. Do not publish; remove its `default` line by hand.")
        return False
    return True


def fnox_get(name: str, profile: Optional[str] = None, env: Optional[dict] = None) -> str:
    r = run(["fnox"] + (["-P", profile] if profile else []) + ["get", name], env=env)
    return r.stdout.strip() if r.returncode == 0 else ""


def cmd_check() -> int:
    text = CONFIG.read_text()
    recips = recipients(text)
    say("Recipients in fnox.toml: " + (", ".join(f"{k} {v[:12]}..." for k, v in recips.items()) or "none yet"))
    have = PERSONAL_KEY.exists() or bool(os.environ.get("FNOX_AGE_KEY"))
    mine = public_key(PERSONAL_KEY) if PERSONAL_KEY.exists() else None
    say(f"Personal key: {PERSONAL_KEY if PERSONAL_KEY.exists() else 'not found'}"
        + ("" if not mine else (" (a recipient)" if mine in recips.values() else " (NOT a recipient: mise run local:secrets:init)")))
    items = encrypted(text)
    if not items:
        say("No encrypted secrets yet. Move yours in with: mise run local:secrets:migrate")
        return 0
    bad = 0
    for name, profile in items:
        ok = bool(fnox_get(name, profile))
        bad += not ok
        say(f"  {'✅' if ok else '❌'} {name:<26} {('profile ' + profile) if profile else 'top level'}")
    if bad:
        say("❌ Some secrets cannot be decrypted here." + ("" if have else " No key found: mise run local:secrets:init"))
    return 1 if bad else 0


def cmd_init() -> int:
    if not PERSONAL_KEY.exists():
        KEY_DIR.mkdir(parents=True, exist_ok=True)
        shown(f"age-keygen > {PERSONAL_KEY}   (mode 600)")
        fd = os.open(PERSONAL_KEY, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(keygen())
        say(f"✅ Made your personal key {PERSONAL_KEY}. Keep a copy in your password manager: without it (and without")
        say("   the CI key) the secrets cannot be read again.")
    key = public_key(PERSONAL_KEY)
    text = CONFIG.read_text()
    if recipients(text).get("personal") == key:
        say(f"✅ Your personal key ({key[:12]}...) is already the `personal` recipient.")
        return 0
    old = recipients(text).get("personal")
    CONFIG.write_text(with_recipient(text, "personal", key))
    shown(f"edit fnox.toml: [providers.age] recipients: personal = {key[:12]}...")
    if old and encrypted(CONFIG.read_text()):
        say("The personal recipient changed: re-encrypting (needs a key that can still decrypt, e.g. FNOX_AGE_KEY).")
        return cmd_reencrypt()
    say("✅ Done. Then: mise run local:secrets:publish")
    return 0


def cmd_set(name: str, profile: Optional[str]) -> int:
    if not recipients(CONFIG.read_text()):
        say("No recipients yet: mise run local:secrets:init")
        return 1
    value = sys.stdin.read().strip("\r\n")
    if not value:
        say("Nothing on stdin: nothing saved.")
        return 1
    return 0 if fnox_set(name, profile, value) else 1


def profiles_with_secrets(text: str) -> List[Optional[str]]:
    return list(dict.fromkeys(p for _, p in encrypted(text)))


def cmd_reencrypt() -> int:
    """fnox re-encrypts one profile at a time (tested): the top level, then each profile that has secrets."""
    ok = True
    for profile in profiles_with_secrets(CONFIG.read_text()):
        cmd = ["fnox"] + (["-P", profile] if profile else []) + ["reencrypt", "-f"]
        shown(" ".join(cmd))
        r = run(cmd)
        ok &= r.returncode == 0
        say(("✅ " if r.returncode == 0 else "❌ ") + (r.stdout.strip() or r.stderr.strip())[:200])
    return 0 if ok else 1


def cmd_ci_key() -> int:
    if run(["gh", "auth", "status"]).returncode != 0:
        say("Sign in to GitHub first: gh auth login")
        return 1
    text = CONFIG.read_text()
    if encrypted(text) and not all(fnox_get(n, p) for n, p in encrypted(text)):
        say("This machine cannot decrypt every secret, so it cannot re-encrypt them for a new CI key. Stopped.")
        return 1
    identity = keygen()
    key = PUBLIC.search(identity).group(0)
    private = next(l for l in identity.splitlines() if l.startswith("AGE-SECRET-KEY-"))
    repo = run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).stdout.strip()
    shown(f"gh secret set {GH_SECRET} --repo {repo}   (the new CI private key, from stdin; it is kept nowhere else)")
    r = run(["gh", "secret", "set", GH_SECRET, "--repo", repo], input=private)
    if r.returncode != 0:
        say(f"❌ Could not set the GitHub secret: {r.stderr.strip()[:200]}")
        return 1
    CONFIG.write_text(with_recipient(text, "ci", key))
    shown(f"edit fnox.toml: [providers.age] recipients: ci = {key[:12]}...")
    if cmd_reencrypt() != 0:
        return 1
    say(f"✅ New CI key: the GitHub secret {GH_SECRET} is set and fnox.toml is encrypted for it. Publish it now, or the")
    say("   workflows cannot read the secrets: mise run local:secrets:publish")
    return 0


def cmd_migrate() -> int:
    if not recipients(CONFIG.read_text()):
        say("No recipients yet: mise run local:secrets:init (and ci-key) first.")
        return 1
    if not LOCAL.exists():
        say("No fnox.local.toml: nothing to move.")
        return 0
    found = local_secrets(LOCAL.read_text())
    if not found:
        say("fnox.local.toml holds no secrets any more (only settings): nothing to move.")
        return 0
    original = LOCAL.read_text()
    # take the values out of fnox.local.toml FIRST (they stay in memory): see fnox_set
    LOCAL.write_text(without_local(original, [(n, p) for n, p, _ in found]))
    os.chmod(LOCAL, 0o600)
    shown("edit fnox.local.toml: removed " + ", ".join(n + (f" ({p})" if p else "") for n, p, _ in found))
    moved = [(n, p) for n, p, value in found if fnox_set(n, p, value)]
    if len(moved) < len(found):
        LOCAL.write_text(original)   # nothing is lost: the local file is back as it was
        os.chmod(LOCAL, 0o600)
        say("fnox.local.toml is restored as it was.")
    bad = [n for n, p in moved if not fnox_get(n, p)]
    say(f"{'✅' if not bad and len(moved) == len(found) else '❌'} Moved {len(moved)} of {len(found)} secrets into fnox.toml"
        + (f"; cannot read back: {', '.join(bad)}" if bad else "") + ". Then: mise run local:secrets:publish")
    return 0 if not bad and len(moved) == len(found) else 1


def cmd_publish(yes: bool) -> int:
    if not run(["git", "status", "--porcelain", "--", "fnox.toml"]).stdout.strip():
        say("fnox.toml has no changes to publish.")
        return 0
    branch = run(["git", "branch", "--show-current"]).stdout.strip()
    if branch != "main":
        say(f"You are on {branch!r}. Secret changes go straight to main: switch to main (git switch main) and run this again.")
        return 1
    leaks = [n for n, _, _ in local_secrets(CONFIG.read_text())]
    if leaks:
        say(f"❌ fnox.toml has PLAIN values for {', '.join(leaks)}. Not publishing. Encrypt them with set/migrate.")
        return 1
    if not yes:
        if not sys.stdin.isatty():
            say("Add --yes to commit and push without asking.")
            return 1
        if not input("Commit fnox.toml (encrypted values only) and push it to main? [y/N] ").strip().lower().startswith("y"):
            say("Not published.")
            return 1
    shown('git commit -m "Secrets: update encrypted values" -- fnox.toml && git push origin main')
    r = run(["git", "commit", "-q", "-m", "Secrets: update encrypted values (fnox.toml, age)", "--", "fnox.toml"])
    if r.returncode != 0:
        say(f"❌ git commit failed: {r.stderr.strip()[:200]}")
        return 1
    r = run(["git", "push", "-q", "origin", "main"])
    if r.returncode != 0:
        say(f"❌ git push failed (pull first?): {r.stderr.strip()[:200]}")
        return 1
    say("✅ Published to main.")
    return 0


def cmd_with_key(cmd: List[str]) -> int:
    env = dict(os.environ)
    if not env.get("FNOX_AGE_KEY") and PERSONAL_KEY.exists():
        env["FNOX_AGE_KEY"] = next((l for l in PERSONAL_KEY.read_text().splitlines()
                                    if l.startswith("AGE-SECRET-KEY-")), "")
    if not cmd:
        say("usage: secrets.py with-key CMD ...")
        return 2
    os.execvpe(cmd[0], cmd, env)
    return 0


def main(argv: List[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    command, rest = argv[0], argv[1:]
    if command == "check":
        return cmd_check()
    if command == "init":
        return cmd_init()
    if command == "set" and rest:
        return cmd_set(rest[0], rest[1] if len(rest) > 1 else None)
    if command == "ci-key":
        return cmd_ci_key()
    if command == "reencrypt":
        return cmd_reencrypt()
    if command == "migrate":
        return cmd_migrate()
    if command == "publish":
        return cmd_publish("--yes" in rest)
    if command == "with-key":
        return cmd_with_key(rest[1:] if rest[:1] == ["--"] else rest)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
