#!/usr/bin/env python3
"""YouTube login cookies for yt-dlp: a logged-in browser gets past YouTube's "Sign in to confirm you're not a bot".

  cookies_setup.py                      ask where the cookies are (a browser, or a cookies.txt you exported), save them
  cookies_setup.py --browser chrome [--profile "Profile 2"]     read them from that browser, no questions
  cookies_setup.py --file cookies.txt   use an exported cookies.txt, no questions
  cookies_setup.py --check              test the saved cookies again

Only cookies of youtube.com and google.com are kept: the file is written without anything else from your browser.
It goes OUTSIDE the repository (~/.config/seeker/youtube-cookies.txt, mode 600), and the path is saved as the local
fnox profile `cookies` in the git-ignored fnox.local.toml, so your own runs use no cookies unless you pick it:
`mise run local:profile:use -- ytdlp proxy cookies`. Cookie values are never printed. Only yt-dlp uses cookies
(youtube-transcript-api has no cookie option).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from http.cookiejar import LoadError
from pathlib import Path
from typing import Dict, List, Optional

from yt_dlp.cookies import SUPPORTED_BROWSERS, YoutubeDLCookieJar, extract_cookies_from_browser

ROOT = Path(__file__).resolve().parents[1]
LOCAL_FILE = ROOT / "fnox.local.toml"
PROFILE = "cookies"
NAME = "YTDLP_COOKIES_FILE"
DEST = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "seeker" / "youtube-cookies.txt"
DOMAINS = ("youtube.com", "google.com")
LOGIN = ("SID", "__Secure-1PSID", "__Secure-3PSID", "SAPISID", "LOGIN_INFO")  # present only when signed in
VIDEO = "HyF6HAlId7g"   # has automatic captions; blocked from GitHub's runners (2026-10-18)
TRIES = 4               # a rotating proxy gives a different address each time, so one try says little
COMMENT = f"# YouTube login cookies (mise run local:cookies:setup). Used only when you pick the `{PROFILE}` profile."

INTRO = """Cookies are a saved Google login. Use a THROWAWAY Google account (not your own): yt-dlp's authors warn that
accounts used this way can be flagged or banned. Sign in to YouTube with it in a separate browser profile first.
Only YouTube and Google cookies are kept, in a file outside this repository (mode 600). Values are never printed."""


def wanted(domain: str) -> bool:
    d = domain.lstrip(".").lower()
    return any(d == s or d.endswith("." + s) for s in DOMAINS)


def only_youtube(jar) -> YoutubeDLCookieJar:
    out = YoutubeDLCookieJar()
    for cookie in jar:
        if wanted(cookie.domain):
            out.set_cookie(cookie)
    return out


def describe(jar, now: Optional[float] = None) -> Dict[str, object]:
    """Counts and the login cookies by NAME (never values); days_left is for the soonest-expiring login cookie."""
    now = time.time() if now is None else now
    login = [c for c in jar if c.name in LOGIN]
    dated = [c.expires for c in login if c.expires]
    return {"cookies": len(list(jar)),
            "login": sorted({c.name for c in login}),
            "expired": sorted({c.name for c in login if c.expires and c.expires < now}),
            "days_left": int((min(dated) - now) // 86400) if dated else None}


def read_file(path: Path):
    jar = YoutubeDLCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)
    return jar


def write_cookies(jar, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(dest.parent, 0o700)
    os.close(os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600))   # exists with mode 600 before any data
    jar.save(str(dest), ignore_discard=True, ignore_expires=True)
    os.chmod(dest, 0o600)


def with_profile(text: str, value: str) -> str:
    """fnox.local.toml text with [profiles.cookies.secrets] holding YTDLP_COOKIES_FILE = value (replacing an old one)."""
    kept: List[str] = []
    skipping = False
    for line in text.splitlines():
        if line.strip() == f"[profiles.{PROFILE}.secrets]":
            skipping = True
            while kept and kept[-1].startswith("# YouTube login cookies"):
                kept.pop()
            continue
        if skipping and (line.startswith("[") or line.startswith("#")):
            skipping = False
        if not skipping:
            kept.append(line)
    body = "\n".join(kept).rstrip("\n")
    block = [COMMENT, f"[profiles.{PROFILE}.secrets]", f"{NAME} = {{ default = {json.dumps(value)} }}"]
    return (body + "\n\n" if body else "") + "\n".join(block) + "\n"


def save_profile(value: str) -> None:
    text = LOCAL_FILE.read_text() if LOCAL_FILE.exists() else ""
    LOCAL_FILE.write_text(with_profile(text, value))
    os.chmod(LOCAL_FILE, 0o600)


def fnox_get(profile: str, name: str) -> str:
    try:
        r = subprocess.run(["fnox", "-P", profile, "get", name], capture_output=True, text=True, cwd=ROOT, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def say(text: str = "") -> None:
    print(text, flush=True)


def shown(cmd: str) -> None:
    print(f"  \033[2m$ {cmd}\033[0m", file=sys.stderr, flush=True)


def ask(prompt: str, default: str = "") -> str:
    answer = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return answer or default


def check_once(env: Dict[str, str]) -> "tuple[bool, str]":
    shown(f"seeker transcripts --method ytdlp check {VIDEO}")
    try:
        r = subprocess.run(["uv", "run", "--no-sync", "seeker", "transcripts", "--method", "ytdlp", "check", VIDEO],
                           env=env, cwd=ROOT, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return False, "timed out"
    lines = [x.strip() for x in (r.stdout + "\n" + r.stderr).splitlines() if x.strip()]
    return "available" in lines, (lines[-1][:160] if lines else "no output")


def test_youtube(path: Path) -> bool:
    """From this computer YouTube answers with or without cookies, so that only shows the file loads. The proxy run
    (if a proxy is saved) is the real test: a datacenter address is what gets "Sign in to confirm you're not a bot"."""
    base = {k: v for k, v in os.environ.items() if k not in ("PROXY_URL", "WEBSHARE_PROXY_USERNAME", "WEBSHARE_PROXY_PASSWORD")}
    ok, last = check_once({**base, NAME: str(path)})
    say(("✅" if ok else "❌") + f" with the cookies, from this computer: {'YouTube answers' if ok else last}")
    proxy = fnox_get("proxy", "PROXY_URL")
    if not proxy:
        say("   No proxy saved, so this says little (YouTube also answers a home address without cookies). The real test is")
        say("   from a blocked address: mise run local:proxy:setup, then run this check again.")
        return ok
    passed = sum(check_once({**base, NAME: str(path), "PROXY_URL": proxy})[0] for _ in range(TRIES))
    say(f"{'✅' if passed else '❌'} with the cookies AND the proxy: {passed} of {TRIES} tries got through "
        f"(the proxy alone got through about 2 in 3 on 2026-10-18)")
    return ok and passed > 0


def collect(args) -> Optional[object]:
    """The cookies from a browser or a file, or None (the reason has been printed)."""
    if args.file is None and args.browser is None:
        say(INTRO)
        where = ask("\nWhere are the cookies?  1 = a browser on this computer, 2 = a cookies.txt you exported", "1")
        if where == "2":
            args.file = ask("Path of the cookies.txt")
        else:
            args.browser = ask(f"Browser ({', '.join(sorted(SUPPORTED_BROWSERS))})", "chrome")
            say("Profile: the browser profile signed in to YouTube. Chrome: its folder name, e.g. Default or Profile 2")
            say("(chrome://version shows it as 'Profile Path'). Empty = the default profile.")
            args.profile = ask("Profile", "")
    try:
        if args.file is not None:
            path = Path(args.file).expanduser()
            shown(f"read {path}  (keep only youtube.com and google.com)")
            return read_file(path)
        if args.browser not in SUPPORTED_BROWSERS:
            say(f"❌ Unknown browser {args.browser!r}. Choose one of: {', '.join(sorted(SUPPORTED_BROWSERS))}")
            return None
        shown(f"read the cookies of {args.browser}{f' ({args.profile})' if args.profile else ''}  (keep only youtube.com and google.com)")
        if sys.platform == "darwin" and args.browser != "firefox":
            say("   macOS may now ask to allow access to the browser's Keychain item (\"... Safe Storage\"): choose Allow.")
        return extract_cookies_from_browser(args.browser, args.profile or None)
    except Exception as e:   # a file that does not parse, or yt-dlp's own error types for browsers
        say(f"❌ Could not read the cookies: {str(e)[:300]}")
        if args.file is None and sys.platform == "darwin":
            say("   Safari needs Full Disk Access for your terminal (System Settings > Privacy & Security).")
        say("   Another way: export them with a browser extension (\"Get cookies.txt LOCALLY\") from a private window"
            " signed in to youtube.com, then run again with --file.")
        return None


def verdict(info: Dict[str, object]) -> bool:
    if not info["login"]:
        say(f"❌ {info['cookies']} YouTube/Google cookies found, but none says \"signed in\". Sign in to YouTube in that browser"
            " profile (a private window is best), then run this again.")
        return False
    say(f"✅ {info['cookies']} YouTube/Google cookies; signed-in cookies: {', '.join(info['login'])}")
    if info["expired"]:
        say(f"⚠️  already expired: {', '.join(info['expired'])}. Sign in again and collect fresh ones.")
    if info["days_left"] is not None:
        say(f"   the soonest signed-in cookie expires in {info['days_left']} days (YouTube may end the session sooner)")
    return len(info["expired"]) < len(info["login"])   # at least one signed-in cookie is still good


def run_check() -> int:
    saved = fnox_get(PROFILE, NAME)
    path = Path(saved) if saved else DEST
    if not path.exists():
        say("No cookies saved yet: mise run local:cookies:setup")
        return 1
    try:
        info = describe(read_file(path))
    except (OSError, LoadError) as e:
        say(f"❌ Could not read {path}: {e}")
        return 1
    if path.stat().st_mode & 0o077:
        say(f"⚠️  {path} can be read by other users. Fix: chmod 600 {path}")
    if not verdict(info):
        return 1
    return 0 if test_youtube(path) else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Collect YouTube cookies for yt-dlp (see the top of this file).")
    ap.add_argument("--check", action="store_true", help="test the saved cookies again")
    ap.add_argument("--file", help="use an exported cookies.txt")
    ap.add_argument("--browser", help="read the cookies from this browser: " + ", ".join(sorted(SUPPORTED_BROWSERS)))
    ap.add_argument("--profile", default="", help="the browser profile (Chrome: Default, Profile 2 ...)")
    args = ap.parse_args(argv)
    if args.check:
        return run_check()
    jar = collect(args)
    if jar is None:
        return 1
    kept = only_youtube(jar)
    if not verdict(describe(kept)):
        return 1
    write_cookies(kept, DEST)
    shown(f"write {DEST}  (mode 600, outside the repository)")
    save_profile(str(DEST))
    shown(f"edit fnox.local.toml: [profiles.{PROFILE}.secrets] {NAME} = {DEST}  (git-ignored, mode 600)")
    say("✅ Saved. Use the cookies for one run:")
    say(f"     FNOX_PROFILE={PROFILE} mise run local:transcripts:manage -- --method ytdlp download-missing --limit 5")
    say(f"   or switch them on, with the proxy: mise run local:profile:use -- ytdlp proxy {PROFILE}   (off again: mise run local:profile:use -- ytdlp)")
    return 0 if test_youtube(DEST) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nStopped, nothing saved.")
        sys.exit(1)
