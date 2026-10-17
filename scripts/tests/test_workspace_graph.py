import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "workspace_graph.py"
spec = importlib.util.spec_from_file_location("workspace_graph", SCRIPT)
wg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wg)


def make_package(root: Path, kind: str, name: str, deps=(), entry_points=None, tests=True):
    pkg = root / kind / name
    module = name.replace("-", "_")
    (pkg / "src" / module).mkdir(parents=True)
    if tests:
        (pkg / "tests").mkdir()
        (pkg / "tests" / "test_x.py").write_text("def test_x(): pass\n")
    lines = ["[project]", f'name = "seeker-{name}"', 'version = "1.2.3"',
             "dependencies = [" + ", ".join(f'"{d}>=0.1"' for d in deps) + "]"]
    for group, names in (entry_points or {}).items():
        lines += [f'[project.entry-points."{group}"]'] + [f'{n} = "{module}:{n}"' for n in names]
    (pkg / "pyproject.toml").write_text("\n".join(lines) + "\n")


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.uv.workspace]\nmembers = ["sdks/*", "apps/*", "services/*"]\n')
    make_package(tmp_path, "sdks", "base")
    make_package(tmp_path, "sdks", "mid", deps=["seeker-base", "requests"],
                 entry_points={"seeker.video_sources": ["a", "b"]})
    make_package(tmp_path, "apps", "cli", deps=["seeker-mid"], tests=False)
    return tmp_path


def test_dependencies_come_first_and_requires_is_transitive(workspace):
    pkgs = wg.load_workspace(workspace)
    names = [p.name for p in pkgs]
    assert names.index("seeker-base") < names.index("seeker-mid") < names.index("seeker-cli")
    by = {p.name: p for p in pkgs}
    assert by["seeker-mid"].depends_on == ["seeker-base"]  # third-party requests is not a workspace package
    assert by["seeker-cli"].depends_on == ["seeker-mid"]
    assert by["seeker-cli"].requires == ["seeker-base", "seeker-mid"]


def test_ids_modules_tests_and_plugins(workspace):
    by = {p.name: p for p in wg.load_workspace(workspace)}
    assert by["seeker-base"].id == "sdk-base" and by["seeker-cli"].id == "app-cli"
    assert by["seeker-mid"].module == "mid"
    assert by["seeker-mid"].has_tests and not by["seeker-cli"].has_tests
    assert by["seeker-mid"].plugins == {"seeker.video_sources": ["a", "b"]}


def test_cycle_is_reported(workspace):
    (workspace / "sdks" / "base" / "pyproject.toml").write_text(
        '[project]\nname = "seeker-base"\nversion = "1"\ndependencies = ["seeker-cli"]\n')
    with pytest.raises(ValueError, match="cycle"):
        wg.load_workspace(workspace)


def test_outputs(workspace):
    pkgs = wg.load_workspace(workspace)
    assert "seeker-mid 1.2.3" in wg.to_text(pkgs)
    assert "provides seeker.video_sources: a, b" in wg.to_text(pkgs)
    assert "app_cli --> sdk_mid" in wg.to_mermaid(pkgs)
    assert json.loads(json.dumps([p.to_dict() for p in pkgs]))[0]["id"] == "sdk-base"


def test_real_workspace_matches_the_documented_layout():
    by = {p.name: p for p in wg.load_workspace()}
    assert {"seeker-sdk-core", "seeker-sdk-videos", "seeker-sdk-transcripts", "seeker-cli", "seeker-tui"} <= set(by)
    assert by["seeker-sdk-core"].depends_on == []  # core has no workspace dependencies
    assert set(by["seeker-cli"].requires) >= {"seeker-sdk-core", "seeker-sdk-videos", "seeker-sdk-transcripts"}
    assert all(p.name.startswith("seeker") for p in by.values())


def test_architecture_doc_diagram_is_current():
    doc = (Path(__file__).resolve().parents[2] / "docs" / "architecture.md").read_text()
    diagram = wg.to_mermaid(wg.load_workspace())
    assert diagram in doc, "docs/architecture.md is stale: run `mise run local:workspace:graph -- --mermaid`"
