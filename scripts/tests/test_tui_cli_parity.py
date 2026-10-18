"""The TUI (apps/tui) must stay in sync with the CLI (apps/cli) and the mise tasks.

Nothing here is hand-maintained per option: every TUI action is run through every combination of its fields,
each `mise run <task> -- args` it builds is turned into the real `seeker` command using mise.toml, and that command
is parsed by the real CLI parser. So the test knows exactly which commands, options and tasks the TUI can reach.

When you add a CLI command, a CLI option or a mise task, either reach it from the TUI (apps/tui/src/seeker_tui/app.py)
or add it to the exceptions below WITH a reason. A reason that no longer applies (the thing is reachable now, or no
longer exists) fails too, so the list cannot rot.
"""

import argparse
import shlex
import tomllib
from pathlib import Path

import pytest

from seeker_cli.main import build_parser
from seeker_tui import app as tui

ROOT = Path(__file__).resolve().parents[2]

# CLI options the TUI deliberately does not offer: (command that defines the option, option) -> reason
CLI_EXCEPTIONS = {
    ("videos update", "--rebuild"): "old alias of `videos rebuild`; the menu has a Rebuild action",
    ("videos update", "--master-file"): "the menu always works on data/videos_master.json",
    ("videos update", "--channel-url"): "the menu always uses the channel's default URL",
    ("videos update", "--force"): "only meaningful with --rebuild",
    ("videos rebuild", "--master-file"): "the menu always works on data/videos_master.json",
    ("videos rebuild", "--channel-url"): "the menu always uses the channel's default URL",
    ("videos rebuild", "--no-preserve"): "throws away all manual categorization; too destructive for a menu, use the CLI",
    ("videos manage", "--master-file"): "the menu always works on data/videos_master.json",
    ("transcripts", "--master-file"): "the menu always works on data/videos_master.json",
    ("knowledge process", "--master-file"): "the menu always works on data/videos_master.json",
}
# mise tasks the TUI deliberately does not run -> reason
TASK_EXCEPTIONS = {
    "menu": "it is this menu",
    "local:transcripts:compare": "the menu runs the same compare through local:transcripts:manage (with --format/--final)",
}
SAMPLES = {"video_id": "abc123DEF45", "videos": "abc123DEF45,xyz", "question": "Which verse?", "limit": "5",
           "list_limit": "20", "max_attempts": "7", "max_requests": "3", "k": "4", "categories": "a,b",
           "category": "c", "notes": "n", "name": "demo", "tool": "answer"}


def combinations(action, cap=20000):
    """Every combination of select/check values (and filled/empty optional inputs) the form can produce."""
    out = []

    def walk(i, values):
        if len(out) >= cap:
            return
        if i == len(action.fields):
            out.append(dict(values))
            return
        f = action.fields[i]
        if not f.visible(values):
            walk(i + 1, values)
            return
        if f.kind == "select":
            options = [v for _, v in tui.resolve_choices(f, values)]
        elif f.kind == "check":
            options = [True, False]
        else:
            options = [SAMPLES.get(f.key, "x")] + ([""] if f.optional else [])
        for option in options:
            walk(i + 1, {**values, f.key: option})

    walk(0, tui.default_values(action))
    return out


def mise_tasks():
    tasks = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]
    return {name: (t["run"] if isinstance(t["run"], str) else " ".join(t["run"])) for name, t in tasks.items()}


def seeker_prefix(run: str):
    """`fnox exec -- uv run seeker transcripts` -> ["transcripts"]; None if the task does not run seeker."""
    tokens = shlex.split(run.split("\n")[0])
    return tokens[tokens.index("seeker") + 1:] if "seeker" in tokens else None


def parsers_on_path(parser, args):
    """[(path, parser)] from the top parser down to the leaf that parsed `args`."""
    chain, path = [("", parser)], []
    while True:
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subs or getattr(args, subs[0].dest, None) is None:
            return chain
        name = getattr(args, subs[0].dest)
        parser = subs[0].choices[name]
        path.append(name)
        chain.append((" ".join(path), parser))


def options_of(parser):
    return {o for a in parser._actions
            if not isinstance(a, (argparse._SubParsersAction, argparse._HelpAction)) for o in a.option_strings}


def cli_inventory():
    """leaves: every command path; options: every (defining command, option)."""
    leaves, options = set(), set()

    def walk(parser, path):
        options.update((" ".join(path), o) for o in options_of(parser))
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subs:
            leaves.add(" ".join(path))
        for s in subs:
            for name, sub in s.choices.items():
                walk(sub, path + [name])

    walk(build_parser(), [])
    return leaves, options


def reach():
    """What the TUI can reach: (leaves, options, tasks, invalid commands)."""
    tasks = mise_tasks()
    parser = build_parser()
    leaves, options, used_tasks, invalid = set(), set(), set(), []
    for action in tui.ACTIONS:
        for values in combinations(action):
            argv = action.build(values)
            if argv[:2] != ["mise", "run"]:
                invalid.append((action.id, argv, "not a mise command"))
                continue
            task, extra = argv[2], argv[4:] if len(argv) > 3 and argv[3] == "--" else argv[3:]
            used_tasks.add(task)
            if task not in tasks:
                invalid.append((action.id, argv, f"unknown mise task {task}"))
                continue
            prefix = seeker_prefix(tasks[task])
            if prefix is None:
                continue
            command = prefix + extra
            try:
                args = parser.parse_args(command)
            except SystemExit:
                invalid.append((action.id, argv, "the CLI rejects " + shlex.join(command)))
                continue
            chain = parsers_on_path(parser, args)
            leaves.add(chain[-1][0])
            given = {t.split("=")[0] for t in command if t.startswith("-")}
            for path, p in chain:
                options.update((path, o) for o in given & options_of(p))
    return leaves, options, used_tasks, invalid


@pytest.fixture(scope="module")
def reached():
    return reach()


def test_every_command_the_tui_builds_is_valid(reached):
    invalid = reached[3]
    assert not invalid, "\n".join(f"{a}: {r}  ({shlex.join(c)})" for a, c, r in invalid[:20])


def test_every_cli_command_is_reachable_from_the_tui(reached):
    leaves, _ = cli_inventory()
    missing = sorted(leaves - reached[0])
    assert not missing, f"CLI commands the TUI cannot run: {missing}"


def test_every_cli_option_is_reachable_or_excused(reached):
    _, options = cli_inventory()
    missing = sorted(o for o in options - reached[1] if o not in CLI_EXCEPTIONS)
    assert not missing, "CLI options the TUI cannot set (offer them, or add an exception with a reason):\n" + \
        "\n".join(f"  {path or 'seeker'} {opt}" for path, opt in missing)


def test_cli_exceptions_are_still_needed(reached):
    _, options = cli_inventory()
    stale = [k for k in CLI_EXCEPTIONS if k not in options or k in reached[1]]
    assert not stale, f"remove these exceptions (option gone, or reachable now): {stale}"


def test_every_mise_task_is_reachable_or_excused(reached):
    missing = sorted(set(mise_tasks()) - reached[2] - set(TASK_EXCEPTIONS))
    assert not missing, f"mise tasks the TUI cannot run (offer them, or add an exception with a reason): {missing}"
    stale = [t for t in TASK_EXCEPTIONS if t not in mise_tasks() or t in reached[2]]
    assert not stale, f"remove these task exceptions (task gone, or reachable now): {stale}"
