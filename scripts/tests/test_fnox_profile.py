"""scripts/fnox_profile.py: profiles, the active stack, switching. The last test uses the real fnox."""

import importlib.util
import shutil
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "fnox_profile.py"


@pytest.fixture
def fp(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("fnox_profile", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "fnox.toml").write_text('''
[secrets.KEY]
if_missing = "ignore"
[secrets.MASTER_LIST_METHOD]
if_missing = "ignore"
[secrets.SEEKER_LLM_PROVIDER]
if_missing = "ignore"
[profiles.ytdlp.secrets]
MASTER_LIST_METHOD = { default = "ytdlp" }
[profiles.gemini.secrets]
SEEKER_LLM_PROVIDER = { default = "gemini" }
''')
    (tmp_path / "fnox.local.toml").write_text('''
[secrets]
KEY = { default = "top-secret" }
[profiles.overrides.secrets]
MASTER_LIST_METHOD = { default = "youtube_api" }
[profiles.mine.secrets]
OTHER_TOKEN = { default = "hidden-value" }
[profiles.proxy.secrets]
PROXY_URL = { default = "http://user-rotate:pw@p.webshare.io:80/" }
''')
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "ACTIVE", tmp_path / ".fnox-profile")
    monkeypatch.setattr(module, "FILES", (tmp_path / "fnox.toml", tmp_path / "fnox.local.toml"))
    monkeypatch.delenv("FNOX_PROFILE", raising=False)
    return module


def test_profiles_show_settings_and_never_secret_values(fp):
    found = fp.profiles()
    assert found["ytdlp"] == {"MASTER_LIST_METHOD": "ytdlp"} and found["gemini"] == {"SEEKER_LLM_PROVIDER": "gemini"}
    assert found["mine"] == {"OTHER_TOKEN": "(secret)"}           # not a setting: the value is masked
    assert (fp.kind(found["ytdlp"]), fp.kind(found["gemini"]), fp.kind(found["mine"])) == ("methods", "model", "other")
    assert found["proxy"] == {"PROXY_URL": "(secret)"} and fp.kind(found["proxy"]) == "network"
    assert "KEY" in fp.declared() and "OTHER_TOKEN" in fp.declared()


def test_stack_is_the_choice_then_overrides(fp, capsys):
    assert fp.stack() == ["overrides"]
    assert fp.cmd_use(["ytdlp", "gemini"]) == 0
    assert (fp.ROOT / ".fnox-profile").read_text() == "ytdlp,gemini\n"
    assert fp.stack() == ["ytdlp", "gemini", "overrides"]
    assert fp.cmd_use([]) == 0 and not (fp.ROOT / ".fnox-profile").exists() and fp.stack() == ["overrides"]


def test_unknown_names_are_refused_and_dropped(fp, monkeypatch, capsys):
    assert fp.cmd_use(["nosuch"]) == 2 and fp.cmd_use(["overrides"]) == 2
    monkeypatch.setenv("FNOX_PROFILE", "gemini, nosuch")
    assert fp.active() == ["gemini"] and "ignoring unknown profile 'nosuch'" in capsys.readouterr().err
    monkeypatch.setenv("FNOX_PROFILE", "default")
    assert fp.active() == []


@pytest.mark.skipif(not shutil.which("fnox"), reason="fnox is not installed")
def test_effective_values_with_the_real_fnox(fp):
    # the local `overrides` profile beats a committed profile; secrets are inherited by every profile
    assert fp.effective("MASTER_LIST_METHOD", ["ytdlp"]) == "ytdlp"
    assert fp.effective("MASTER_LIST_METHOD", ["ytdlp", "overrides"]) == "youtube_api"
    assert fp.effective("KEY", ["gemini"]) == "top-secret"
    assert fp.effective("SEEKER_LLM_PROVIDER", []) == ""


def test_cookies_profile_is_a_network_profile(fp):
    assert fp.kind({"YTDLP_COOKIES_BASE64": "IyBOZXRzY2FwZQ=="}) == "network"
