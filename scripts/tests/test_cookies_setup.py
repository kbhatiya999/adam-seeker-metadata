"""scripts/cookies_setup.py: only YouTube/Google cookies are kept, saved as one base64 env value, never shown.
Fake cookie files only; the browser reader is yt-dlp's own and is not run here."""

import base64
import importlib.util
import stat
import subprocess
import time
import tomllib
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "cookies_setup.py"
FAR = int(time.time()) + 200 * 86400
SECRET = "S3CR3T-VALUE"


def netscape(*rows) -> str:
    """rows: (domain, name, expires). Netscape cookies.txt, the format every export extension writes."""
    lines = ["# Netscape HTTP Cookie File"]
    for domain, name, expires in rows:
        lines.append("\t".join([domain, str(domain.startswith(".")).upper(), "/", "TRUE", str(expires), name, SECRET]))
    return "\n".join(lines) + "\n"


SIGNED_IN = netscape((".youtube.com", "LOGIN_INFO", FAR), (".google.com", "SID", FAR), ("accounts.google.com", "OTZ", FAR),
                     (".bank.example", "session", FAR), (".evilyoutube.com", "SID", FAR))
SIGNED_OUT = netscape((".youtube.com", "VISITOR_INFO1_LIVE", FAR), (".bank.example", "session", FAR))


@pytest.fixture
def cs(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("cookies_setup", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "LOCAL_FILE", tmp_path / "fnox.local.toml")

    def saved(profile, name):   # what fnox would give for the profile, read from the fake local file
        try:
            return tomllib.loads(module.LOCAL_FILE.read_text())["profiles"][profile]["secrets"][name]["default"]
        except (OSError, KeyError):
            return ""
    monkeypatch.setattr(module, "fnox_get", saved)
    monkeypatch.setattr(module, "test_youtube", lambda value: True)   # no network in tests
    return module


def saved_text(cs) -> str:
    return base64.b64decode(cs.fnox_get("cookies", "YTDLP_COOKIES_BASE64")).decode()


def test_wanted_domains(cs):
    assert all(cs.wanted(d) for d in (".youtube.com", "youtube.com", "music.youtube.com", "accounts.google.com", ".google.com"))
    assert not any(cs.wanted(d) for d in ("evilyoutube.com", "youtube.com.evil.example", ".bank.example", "google.com.evil.example"))


def test_only_youtube_and_google_are_kept(cs, tmp_path):
    f = tmp_path / "in.txt"
    f.write_text(SIGNED_IN)
    kept = cs.only_youtube(cs.read_file(f))
    assert sorted(c.domain for c in kept) == [".google.com", ".youtube.com", "accounts.google.com"]


def test_describe_shows_names_and_days_never_values(cs, tmp_path):
    f = tmp_path / "in.txt"
    f.write_text(SIGNED_IN)
    info = cs.describe(cs.only_youtube(cs.read_file(f)))
    assert info["login"] == ["LOGIN_INFO", "SID"] and info["expired"] == [] and 198 <= info["days_left"] <= 200
    assert SECRET not in str(info)


def test_expired_login_cookies_are_reported(cs, tmp_path):
    f = tmp_path / "in.txt"
    f.write_text(netscape((".google.com", "SID", int(time.time()) - 86400)))
    info = cs.describe(cs.read_file(f))
    assert info["expired"] == ["SID"] and info["days_left"] < 0
    assert cs.verdict(info) is False


def test_import_saves_one_base64_line_with_only_youtube_cookies(cs, tmp_path, capsys):
    f = tmp_path / "export.txt"
    f.write_text(SIGNED_IN)
    assert cs.main(["--file", str(f)]) == 0
    out = saved_text(cs)
    assert ".youtube.com" in out and "bank.example" not in out and "evilyoutube" not in out
    assert stat.S_IMODE(cs.LOCAL_FILE.stat().st_mode) == 0o600
    value = cs.fnox_get("cookies", "YTDLP_COOKIES_BASE64")
    assert "\n" not in value and SECRET not in capsys.readouterr().out
    assert "[profiles.cookies.secrets]" in cs.LOCAL_FILE.read_text()


def test_not_signed_in_saves_nothing(cs, tmp_path, capsys):
    f = tmp_path / "export.txt"
    f.write_text(SIGNED_OUT)
    assert cs.main(["--file", str(f)]) == 1
    assert not cs.LOCAL_FILE.exists()
    assert "signed in" in capsys.readouterr().out


def test_missing_file_is_a_clear_error(cs, tmp_path, capsys):
    assert cs.main(["--file", str(tmp_path / "nope.txt")]) == 1
    assert "Could not read the cookies" in capsys.readouterr().out


def test_unknown_browser_is_refused(cs, capsys):
    assert cs.main(["--browser", "netscape"]) == 1
    assert "Unknown browser" in capsys.readouterr().out


def test_check_without_saved_cookies(cs, capsys):
    assert cs.main(["--check"]) == 1
    assert "No cookies saved yet" in capsys.readouterr().out


def test_check_after_saving(cs, tmp_path, capsys):
    f = tmp_path / "export.txt"
    f.write_text(SIGNED_IN)
    cs.main(["--file", str(f)])
    capsys.readouterr()
    assert cs.main(["--check"]) == 0
    assert "signed-in cookies: LOGIN_INFO, SID" in capsys.readouterr().out


def test_with_profile_adds_replaces_and_keeps_the_rest(cs):
    text = '[secrets]\nGEMINI_API_KEY = { default = "k" }\n\n[profiles.overrides.secrets]\nTRANSCRIPT_METHOD = { default = "ytdlp" }\n'
    once = cs.with_profile(text, "AAAA")
    twice = cs.with_profile(once, "BBBB")
    assert twice.count("[profiles.cookies.secrets]") == 1 and twice.count("# YouTube login cookies") == 1
    assert "AAAA" not in twice and 'YTDLP_COOKIES_BASE64 = { default = "BBBB" }' in twice
    assert 'GEMINI_API_KEY = { default = "k" }' in twice and 'TRANSCRIPT_METHOD = { default = "ytdlp" }' in twice
    assert cs.with_profile("", "AAAA").startswith("# YouTube login cookies")


def test_with_profile_keeps_a_section_after_ours(cs):
    text = '[profiles.cookies.secrets]\nYTDLP_COOKIES_BASE64 = { default = "OLD" }\n\n# other\n[profiles.proxy.secrets]\nPROXY_URL = { default = "u" }\n'
    out = cs.with_profile(text, "NEW")
    assert "OLD" not in out and "[profiles.proxy.secrets]" in out and 'PROXY_URL = { default = "u" }' in out and "# other" in out


def test_github_gets_the_value_through_stdin_never_the_command_line(cs, tmp_path, monkeypatch):
    f = tmp_path / "export.txt"
    f.write_text(SIGNED_IN)
    cs.main(["--file", str(f)])
    value = cs.fnox_get("cookies", "YTDLP_COOKIES_BASE64")
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        out = "owner/repo\n" if cmd[:3] == ["gh", "repo", "view"] else ""
        return subprocess.CompletedProcess(cmd, 0, out, "")
    monkeypatch.setattr(cs.subprocess, "run", fake_run)
    assert cs.main(["--github"]) == 0
    secret = [c for c in calls if c[0][:3] == ["gh", "secret", "set"]][0]
    assert secret[0] == ["gh", "secret", "set", "YTDLP_COOKIES_BASE64", "--repo", "owner/repo"]
    assert secret[1]["input"] == value and not any(value in " ".join(c[0]) for c in calls)


def test_github_without_saved_cookies(cs, capsys):
    assert cs.main(["--github"]) == 1
    assert "No cookies saved yet" in capsys.readouterr().out
