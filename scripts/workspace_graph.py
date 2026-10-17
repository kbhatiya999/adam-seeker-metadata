#!/usr/bin/env python3
"""Describe the uv workspace: packages, who depends on whom, which plugins each one provides.

    uv run --no-project python scripts/workspace_graph.py            # readable text
    uv run --no-project python scripts/workspace_graph.py --json     # for the Tiltfile
    uv run --no-project python scripts/workspace_graph.py --mermaid  # paste into docs

Everything is read from the pyproject files (members come from `[tool.uv.workspace]`), so a package
added with `mise run sdk:new` shows up here and in the Tilt dashboard without editing anything.
Standard library only.
"""

import argparse
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
KINDS = {"sdks": "sdk", "apps": "app", "services": "service"}


@dataclass
class Package:
    name: str
    version: str
    kind: str  # sdks | apps | services
    dir: str  # relative to the workspace root, e.g. sdks/core
    module: str  # import name, e.g. seeker_sdk_core
    has_tests: bool
    depends_on: List[str] = field(default_factory=list)  # direct workspace dependencies
    requires: List[str] = field(default_factory=list)  # all workspace dependencies, dependencies first
    plugins: Dict[str, List[str]] = field(default_factory=dict)  # entry-point group -> names
    scripts: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Short, unique resource name, e.g. sdk-core, app-cli."""
        return f"{KINDS.get(self.kind, self.kind)}-{Path(self.dir).name}"

    def to_dict(self) -> dict:
        return {**self.__dict__, "id": self.id}


def _requirement_name(req: str) -> str:
    m = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", req.strip())
    return re.sub(r"[-_.]+", "-", m.group(0)).lower() if m else ""


def _members(root: Path) -> List[Path]:
    data = tomllib.loads((root / "pyproject.toml").read_text())
    patterns = data.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    found = {p for pattern in patterns for p in root.glob(pattern) if (p / "pyproject.toml").is_file()}
    return sorted(found)


def load_workspace(root: Path = ROOT) -> List[Package]:
    """All workspace packages, dependencies before dependents. Raises ValueError on a dependency cycle."""
    packages: Dict[str, Package] = {}
    for member in _members(root):
        meta = tomllib.loads((member / "pyproject.toml").read_text())
        project = meta["project"]
        src = [d.name for d in sorted((member / "src").glob("*")) if d.is_dir() and d.name != "__pycache__"]
        tests = member / "tests"
        name = _requirement_name(project["name"])
        packages[name] = Package(
            name=name,
            version=project.get("version", "0"),
            kind=member.parent.name,
            dir=member.relative_to(root).as_posix(),
            module=src[0] if src else name.replace("-", "_"),
            has_tests=tests.is_dir() and any(tests.glob("test_*.py")),
            plugins={g: sorted(eps) for g, eps in project.get("entry-points", {}).items()},
            scripts=sorted(project.get("scripts", {})),
        )
        packages[name].depends_on = [_requirement_name(r) for r in project.get("dependencies", [])]
    for p in packages.values():
        p.depends_on = sorted(d for d in set(p.depends_on) if d in packages and d != p.name)

    ordered: List[str] = []
    state: Dict[str, int] = {}  # 1 = visiting, 2 = done

    def visit(name: str, trail: List[str]) -> None:
        if state.get(name) == 2:
            return
        if state.get(name) == 1:
            raise ValueError("dependency cycle: " + " -> ".join(trail + [name]))
        state[name] = 1
        for dep in packages[name].depends_on:
            visit(dep, trail + [name])
        state[name] = 2
        ordered.append(name)

    for name in sorted(packages):
        visit(name, [])
    for name in ordered:
        requires: List[str] = []
        for dep in packages[name].depends_on:
            for r in packages[dep].requires + [dep]:
                if r not in requires:
                    requires.append(r)
        packages[name].requires = [n for n in ordered if n in requires]
    return [packages[n] for n in ordered]


def to_text(packages: List[Package]) -> str:
    lines = []
    for kind in KINDS:
        members = [p for p in packages if p.kind == kind]
        if not members:
            continue
        lines.append(f"{kind}/")
        for p in members:
            lines.append(f"  {p.name} {p.version}  ({p.dir}, import {p.module})")
            if p.depends_on:
                lines.append(f"      depends on: {', '.join(p.depends_on)}")
            for group, names in p.plugins.items():
                lines.append(f"      provides {group}: {', '.join(names)}")
            for s in p.scripts:
                lines.append(f"      command: {s}")
            if not p.has_tests:
                lines.append("      (no tests yet)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_mermaid(packages: List[Package]) -> str:
    node = lambda p: p.id.replace("-", "_")  # noqa: E731
    lines = ["graph LR"]
    for kind in KINDS:
        members = [p for p in packages if p.kind == kind]
        if members:
            lines.append(f"  subgraph {kind}")
            lines += [f'    {node(p)}["{p.name}"]' for p in members]
            lines.append("  end")
    by_name = {p.name: p for p in packages}
    for p in packages:
        lines += [f"  {node(p)} --> {node(by_name[d])}" for d in p.depends_on]
    return "\n".join(lines) + "\n"


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    fmt = ap.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true", help="machine readable (used by the Tiltfile)")
    fmt.add_argument("--mermaid", action="store_true", help="Mermaid diagram")
    args = ap.parse_args(argv)
    try:
        packages = load_workspace()
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"packages": [p.to_dict() for p in packages]}, indent=2))
    elif args.mermaid:
        print(to_mermaid(packages), end="")
    else:
        print(to_text(packages), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
