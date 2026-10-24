"""scripts/secrets.py: the recipients block, what counts as a secret, migrating fnox.local.toml, refusing plain values.
The last test runs the real fnox and age-keygen with throwaway keys in a temporary folder (skipped without them)."""

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "secrets.py"
ME = "age1" + "q" * 58
CI = "age1" + "p" * 58
CI2 = "age1" + "z" * 58


@pytest.fixture
def sc(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("seeker_secrets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "CONFIG", tmp_path / "fnox.toml")
    monkeypatch.setattr(module, "LOCAL", tmp_path / "fnox.local.toml")
    return module


BASE = '''# header
[secrets.YOUTUBE_API_KEY]
if_missing = "warn"

[profiles.ytdlp.secrets]
MASTER_LIST_METHOD = { default = "ytdlp" }
'''


def test_recipients_block_is_added_before_the_secrets_and_replaced_by_label(sc):
    once = sc.with_recipient(BASE, "personal", ME)
    assert once.index("[providers.age]") < once.index("[secrets.YOUTUBE_API_KEY]") and once.startswith("# header")
    both = sc.with_recipient(once, "ci", CI)
    assert sc.recipients(both) == {"personal": ME, "ci": CI}
    swapped = sc.with_recipient(both, "ci", CI2)
    assert sc.recipients(swapped) == {"personal": ME, "ci": CI2} and swapped.count("[providers.age]") == 1
    assert CI not in swapped and 'MASTER_LIST_METHOD = { default = "ytdlp" }' in swapped


def test_personal_stays_first(sc):
    text = sc.with_recipient(sc.with_recipient(BASE, "ci", CI), "personal", ME)
    assert list(sc.recipients(text)) == ["personal", "ci"]


def test_encrypted_lists_top_level_and_profile_secrets(sc):
    text = BASE + '''
[secrets.GEMINI_API_KEY]
provider = "age"
value = "x"

[profiles.proxy.secrets]
PROXY_URL = { provider = "age", value = "y" }
'''
    assert sc.encrypted(text) == [("GEMINI_API_KEY", None), ("PROXY_URL", "proxy")]


LOCAL = '''[secrets]
GEMINI_API_KEY = { default = "g" }
YOUTUBE_API_KEY = { default = "y" }

[profiles.overrides.secrets]
TRANSCRIPT_METHOD = { default = "ytdlp" }

# Webshare rotating proxy (mise run local:proxy:setup). Used only when you pick the `proxy` profile.
[profiles.proxy.secrets]
WEBSHARE_PROXY_USERNAME = { default = "u" }
PROXY_URL = { default = "http://u-rotate:p@p.webshare.io:80/" }
'''


def test_local_secrets_leave_settings_alone(sc):
    found = sc.local_secrets(LOCAL)
    assert [(n, p) for n, p, _ in found] == [("GEMINI_API_KEY", None), ("YOUTUBE_API_KEY", None),
                                             ("WEBSHARE_PROXY_USERNAME", "proxy"), ("PROXY_URL", "proxy")]


def test_without_local_drops_moved_lines_and_empty_sections(sc):
    out = sc.without_local(LOCAL, [(n, p) for n, p, _ in sc.local_secrets(LOCAL)])
    assert out == '[profiles.overrides.secrets]\nTRANSCRIPT_METHOD = { default = "ytdlp" }\n'


def test_without_local_keeps_what_was_not_moved(sc):
    out = sc.without_local(LOCAL, [("GEMINI_API_KEY", None), ("PROXY_URL", "proxy")])
    assert "GEMINI_API_KEY" not in out and "PROXY_URL" not in out
    assert 'YOUTUBE_API_KEY = { default = "y" }' in out and "WEBSHARE_PROXY_USERNAME" in out and "[profiles.proxy.secrets]" in out


def test_publish_refuses_plain_values(sc, monkeypatch, capsys):
    sc.CONFIG.write_text('[secrets.YOUTUBE_API_KEY]\ndefault = "plain-key"\n')
    answers = {("git", "status"): " M fnox.toml\n", ("git", "branch"): "main\n"}
    monkeypatch.setattr(sc, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, answers.get(tuple(cmd[:2]), ""), ""))
    assert sc.cmd_publish(yes=True) == 1
    assert "PLAIN values for YOUTUBE_API_KEY" in capsys.readouterr().out


def test_publish_only_from_main(sc, monkeypatch, capsys):
    sc.CONFIG.write_text(BASE)
    answers = {("git", "status"): " M fnox.toml\n", ("git", "branch"): "feature\n"}
    monkeypatch.setattr(sc, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, answers.get(tuple(cmd[:2]), ""), ""))
    assert sc.cmd_publish(yes=True) == 1
    assert "straight to main" in capsys.readouterr().out


def _age_keygen():
    exe = shutil.which("age-keygen")
    if exe:
        return [exe]
    r = subprocess.run(["mise", "which", "age-keygen"], capture_output=True, text=True)
    return [r.stdout.strip()] if r.returncode == 0 and r.stdout.strip() else None


@pytest.mark.skipif(not shutil.which("fnox"), reason="needs fnox")
def test_real_fnox_both_keys_decrypt_and_migrate_moves_values(tmp_path):
    keygen = _age_keygen()
    if not keygen:
        pytest.skip("needs age-keygen (mise install)")
    home = tmp_path / "fnoxcfg"
    home.mkdir()
    subprocess.run(keygen + ["-o", str(home / "age.txt")], check=True, capture_output=True)
    ci = subprocess.run(keygen, check=True, capture_output=True, text=True).stdout
    project = tmp_path / "repo"
    (project / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, project / "scripts" / "secrets.py")
    (project / "fnox.toml").write_text(BASE)
    (project / "fnox.local.toml").write_text(LOCAL)
    env = {**os.environ, "FNOX_CONFIG_DIR": str(home), "FNOX_NO_DAEMON": "1"}
    env.pop("FNOX_AGE_KEY", None)
    env.pop("FNOX_AGE_KEY_FILE", None)

    def go(*args, **kw):
        return subprocess.run(["python3", "scripts/secrets.py", *args], cwd=project, env=env, text=True, capture_output=True, **kw)

    assert go("init").returncode == 0
    text = (project / "fnox.toml").read_text()
    ci_public = next(l.split(": ")[1] for l in ci.splitlines() if l.startswith("# public key"))
    spec = importlib.util.spec_from_file_location("s2", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (project / "fnox.toml").write_text(mod.with_recipient(text, "ci", ci_public))
    r = go("migrate")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "TRANSCRIPT_METHOD" in (project / "fnox.local.toml").read_text()
    assert "GEMINI_API_KEY" not in (project / "fnox.local.toml").read_text()
    stored = (project / "fnox.toml").read_text()
    assert '"g"' not in stored and "http://u-rotate" not in stored   # only ciphertext is committed

    def get(name, profile=None, **extra):
        cmd = ["fnox", "--no-daemon"] + (["-P", profile] if profile else []) + ["get", name]
        return subprocess.run(cmd, cwd=project, env={**env, **extra}, text=True, capture_output=True).stdout.strip()

    assert get("GEMINI_API_KEY") == "g" and get("PROXY_URL", "proxy") == "http://u-rotate:p@p.webshare.io:80/"
    ci_private = next(l for l in ci.splitlines() if l.startswith("AGE-SECRET-KEY-"))
    ci_only = {"FNOX_CONFIG_DIR": str(tmp_path / "nothing"), "FNOX_AGE_KEY": ci_private}
    assert get("YOUTUBE_API_KEY", **ci_only) == "y" and get("WEBSHARE_PROXY_USERNAME", "proxy", **ci_only) == "u"
    assert go("check").returncode == 0
