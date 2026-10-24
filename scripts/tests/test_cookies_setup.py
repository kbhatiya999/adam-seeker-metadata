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
    module.store, module.calls = {}, []   # a fake fnox: what `secrets.py set` was given, by (profile, name)
    real_run = module.subprocess.run

    def fake_run(cmd, **kw):
        if len(cmd) > 2 and str(cmd[1]).endswith("secrets.py") and cmd[2] == "set":
            module.calls.append((cmd, kw))
            module.store[(cmd[4], cmd[3])] = kw["input"]
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, **kw)
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "fnox_get", lambda profile, name: module.store.get((profile, name), ""))
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
    value = cs.fnox_get("cookies", "YTDLP_COOKIES_BASE64")
    assert "\n" not in value and SECRET not in capsys.readouterr().out
    (cmd, kw), = cs.calls   # encrypted through secrets.py, the value on stdin and never on the command line
    assert cmd[2:] == ["set", "YTDLP_COOKIES_BASE64", "cookies"] and kw["input"] == value
    assert not any(value in str(x) for x in cmd)


def test_not_signed_in_saves_nothing(cs, tmp_path, capsys):
    f = tmp_path / "export.txt"
    f.write_text(SIGNED_OUT)
    assert cs.main(["--file", str(f)]) == 1
    assert cs.store == {}
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
