#!/usr/bin/env python3
"""
Terminal UI over the mise tasks: pick where to run (local / act / gh), what to run and its
options, instead of remembering task names. It shows the exact command before running it,
asks for confirmation before anything that publishes (gh) or is heavy (rebuild, nuke without
--dry-run), and runs the command in the real terminal (so prompts, e.g. API key setup, work).

    mise run menu
"""

import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, OptionList, Select, Static
from textual.widgets.option_list import Option

Values = Dict[str, Any]
Choices = Union[Sequence[Tuple[str, str]], Callable[[Values], Sequence[Tuple[str, str]]]]

WHERE = [
    ("local - run the script on this machine", "local"),
    ("act - run the GitHub workflow in Docker (publishes nothing)", "act"),
    ("gh - trigger the REAL GitHub workflow", "gh"),
]
WHERE_NO_GH = WHERE[:2]
TRANSCRIPT_METHODS = [("ytdlp", "ytdlp"), ("youtube_transcript_api", "youtube_transcript_api")]
SETTINGS = [("master-list - how new videos are found", "master-list"),
            ("transcript - how transcripts are fetched", "transcript")]


def mise(task: str, *args: str) -> List[str]:
    return ["mise", "run", task] + (["--"] + list(args) if args else [])


@dataclass
class Field:
    key: str
    label: str
    kind: str  # select | input | check
    choices: Choices = ()
    default: Any = ""
    visible: Callable[[Values], bool] = lambda v: True


@dataclass
class Action:
    id: str
    group: str
    label: str
    description: str
    build: Callable[[Values], List[str]]
    fields: List[Field] = field(default_factory=list)
    danger: Callable[[Values], Optional[str]] = lambda v: None


GH_WARN = "This triggers the REAL workflow on GitHub: it commits to the repo and comments on or creates issues."


def method_choices(v: Values):
    if v.get("setting") == "transcript":
        return TRANSCRIPT_METHODS + [("unset (remove the setting)", "unset")]
    return [("youtube_api", "youtube_api"), ("ytdlp", "ytdlp"), ("unset (remove the setting)", "unset")]


def _manage_build(v: Values) -> List[str]:
    c = v["cmd"]
    if c == "categorize":
        return mise("local:videos:manage", "categorize", v["video_id"], "--categories", v["categories"],
                    "--relevance", v["relevance"])
    if c == "priority":
        return mise("local:videos:manage", "priority", v["video_id"], "--category", v["category"])
    return mise("local:videos:manage", c)


def _transcripts_build(v: Values) -> List[str]:
    c = v["cmd"]
    fmt = []
    if c in ("download-missing", "download", "compare"):
        if v.get("format"):
            fmt += ["--format", v["format"]]
        if v.get("final"):
            fmt += ["--final", v["final"]]
    if c in ("stats", "list-missing"):
        return mise("local:transcripts:manage", c)
    if c == "compare":
        return mise("local:transcripts:manage", *fmt, "compare", v["video_id"])
    if c == "download-missing":
        return mise("local:transcripts:manage", "--method", v["method"], *fmt, c, "--limit", v["limit"])
    return mise("local:transcripts:manage", "--method", v["method"], *fmt, c, v["video_id"])


def _nuke_build(v: Values) -> List[str]:
    flags = [f for f, k in (("--dry-run", "dry"), ("--all", "all"), ("--yes", "yes")) if v.get(k)]
    return mise("nuke", *flags)


def _nuke_danger(v: Values) -> Optional[str]:
    if v.get("dry"):
        return None
    if v.get("yes"):
        return "--yes skips nuke's own confirmation and deletes right away."
    return None


ACTIONS: List[Action] = [
    Action("update", "Videos", "Update videos", "Fetch new videos and update data/videos_master.json.",
           lambda v: mise(f"{v['where']}:videos:update"),
           [Field("where", "Where to run it", "select", WHERE, "local")],
           lambda v: GH_WARN if v["where"] == "gh" else None),
    Action("rebuild", "Videos", "Rebuild videos",
           "Rebuild the master list from YouTube (private videos are dropped).",
           lambda v: mise(f"{v['where']}:videos:rebuild"),
           [Field("where", "Where to run it", "select", WHERE, "local")],
           lambda v: (GH_WARN + " " if v["where"] == "gh" else "") +
           "A rebuild replaces the whole master list; videos that are no longer public disappear."),
    Action("manage", "Videos", "Manage / categorize videos", "Report, list uncategorized, categorize, set priority.",
           _manage_build,
           [Field("cmd", "What", "select",
                  [(c, c) for c in ("report", "list-uncategorized", "interactive", "categorize", "priority")], "report"),
            Field("video_id", "Video ID", "input", visible=lambda v: v["cmd"] in ("categorize", "priority")),
            Field("categories", "Categories (comma separated)", "input", visible=lambda v: v["cmd"] == "categorize"),
            Field("relevance", "Relevance 1-10", "select", [(str(i), str(i)) for i in range(10, 0, -1)], "5",
                  lambda v: v["cmd"] == "categorize"),
            Field("category", "Category", "input", visible=lambda v: v["cmd"] == "priority")]),
    Action("transcripts", "Transcripts", "Transcripts",
           "Download or inspect transcripts. The method is explicit, with no fallback.",
           _transcripts_build,
           [Field("cmd", "What", "select",
                  [(c, c) for c in ("stats", "list-missing", "download-missing", "download", "check", "compare")],
                  "stats"),
            Field("method", "Method", "select", TRANSCRIPT_METHODS, "youtube_transcript_api",
                  lambda v: v["cmd"] in ("download-missing", "download", "check")),
            Field("format", "Format to DOWNLOAD (both methods; ttml/srv1/srt are small, vtt is large)", "select",
                  [("ttml", "ttml"), ("srv1", "srv1"), ("srt", "srt"), ("vtt", "vtt")], "ttml",
                  lambda v: v["cmd"] in ("download-missing", "download", "compare")),
            Field("final", "FINAL files (the post-processor converts into these)", "select",
                  [("srt + txt", "srt,txt"), ("txt only", "txt"), ("srt only", "srt"), ("vtt + txt", "vtt,txt"),
                   ("srt + vtt + txt", "srt,vtt,txt")], "srt,txt",
                  lambda v: v["cmd"] in ("download-missing", "download", "compare")),
            Field("limit", "How many videos", "input", default="5", visible=lambda v: v["cmd"] == "download-missing"),
            Field("video_id", "Video ID", "input", visible=lambda v: v["cmd"] in ("download", "check", "compare"))]),
    Action("method-set", "Methods", "Change a method",
           "Set master-list or transcript method for local, act or the real GitHub workflows.",
           lambda v: mise(f"{v['where']}:method:set", v["setting"], v["value"]),
           [Field("where", "Change it where", "select",
                  [("local - fnox.local.toml (local tasks)", "local"), ("act - .vars (act tasks)", "act"),
                   ("gh - repository variable (real workflows)", "gh")], "local"),
            Field("setting", "Setting", "select", SETTINGS, "master-list"),
            Field("value", "Value", "select", method_choices, "ytdlp")],
           lambda v: "This changes a REPOSITORY VARIABLE used by the real GitHub workflows." if v["where"] == "gh" else None),
    Action("method-show", "Methods", "Show current methods", "Show the methods currently set.",
           lambda v: mise(f"{v['where']}:method:show"),
           [Field("where", "Show for", "select",
                  [("local", "local"), ("act", "act"), ("gh", "gh")], "local")]),
    Action("apikey", "Setup", "Get a YouTube API key",
           "Guided setup with gcloud (you sign in) or the console; validates and saves the key.",
           lambda v: mise("local:apikey:setup")),
    Action("install", "Setup", "First-time install", "Install tools, sync Python deps, check Docker.",
           lambda v: mise("install")),
    Action("docker", "Docker", "Docker", "Start, stop, diagnose or clean up Docker for the act tasks.",
           lambda v: mise(f"docker:{v['what']}"),
           [Field("what", "What", "select",
                  [("diagnose - host vs Docker resources and how to change them", "diagnose"),
                   ("start", "start"), ("stop", "stop"),
                   ("cleanup - remove this project's leftover containers/volumes", "cleanup")], "diagnose")]),
    Action("nuke", "Danger", "Nuke", "Remove what this project created (.venv, .act, Docker leftovers; --all for more).",
           _nuke_build,
           [Field("dry", "--dry-run (only show what would be removed)", "check", default=True),
            Field("all", "--all (also uv cache, act-toolcache, pinned mise tools, fnox.local.toml)", "check"),
            Field("yes", "--yes (skip nuke's own prompt)", "check")],
           _nuke_danger),
]


def default_values(action: Action) -> Values:
    out: Values = {}
    for f in action.fields:
        out[f.key] = f.default
    return out


def resolve_choices(f: Field, values: Values) -> List[Tuple[str, str]]:
    return list(f.choices(values) if callable(f.choices) else f.choices)


def default_runner(argv: List[str]) -> int:
    print("\n\033[2m$ " + shlex.join(argv) + "\033[0m\n")
    try:
        rc = subprocess.run(argv).returncode
    except KeyboardInterrupt:
        rc = 130
    print("\n" + ("\033[32m✔ finished\033[0m" if rc == 0 else f"\033[31m✘ exit code {rc}\033[0m"))
    try:
        input("\nPress Enter to return to the menu... ")
    except EOFError:
        pass
    return rc


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("y", "yes", "Yes"), Binding("n,escape", "no", "No")]
    DEFAULT_CSS = """
    ConfirmScreen { align: center middle; }
    #box { width: 70; padding: 1 2; border: thick $error; background: $surface; height: auto; }
    #warn { color: $error; text-style: bold; margin-bottom: 1; }
    """

    def __init__(self, warning: str, command: str):
        super().__init__()
        self.warning, self.command = warning, command

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static("⚠  " + self.warning, id="warn")
            yield Static("$ " + self.command)
            yield Label("")
            with Horizontal():
                yield Button("Yes, run it (y)", id="yes", variant="error")
                yield Button("Cancel (n)", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class FormScreen(ModalScreen[Optional[List[str]]]):
    BINDINGS = [Binding("escape", "cancel", "Back")]
    DEFAULT_CSS = """
    FormScreen { align: center middle; }
    #form { width: 90; max-height: 90%; padding: 1 2; border: thick $accent; background: $surface; }
    #preview { margin-top: 1; padding: 0 1; background: $boost; }
    #warning { color: $error; text-style: bold; margin-top: 1; }
    .row { height: auto; margin-bottom: 1; }
    """

    def __init__(self, action: Action):
        super().__init__()
        self.action = action
        self.values: Values = default_values(action)
        self._building = True

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="form"):
            yield Static(f"[b]{self.action.label}[/b]\n{self.action.description}")
            for f in self.action.fields:
                with Vertical(classes="row", id=f"row-{f.key}"):
                    if f.kind == "select":
                        opts = resolve_choices(f, self.values)
                        yield Label(f.label)
                        yield Select(opts, value=f.default if any(v == f.default for _, v in opts) else opts[0][1],
                                     allow_blank=False, id=f"f-{f.key}")
                    elif f.kind == "input":
                        yield Label(f.label)
                        yield Input(value=str(f.default), id=f"f-{f.key}")
                    else:
                        yield Checkbox(f.label, value=bool(f.default), id=f"f-{f.key}")
            yield Static("", id="preview")
            yield Static("", id="warning")
            with Horizontal():
                yield Button("Run", id="run", variant="primary")
                yield Button("Back", id="back")

    def on_mount(self) -> None:
        self._building = False
        self._refresh()

    def _read(self) -> None:
        for f in self.action.fields:
            w = self.query_one(f"#f-{f.key}")
            self.values[f.key] = w.value if not isinstance(w, Select) or w.value is not Select.BLANK else ""

    def _refresh(self) -> None:
        if self._building:
            return
        self._building = True
        try:
            self._read()
            # dependent choices (e.g. method values depend on the setting)
            for f in self.action.fields:
                if f.kind == "select" and callable(f.choices):
                    sel = self.query_one(f"#f-{f.key}", Select)
                    opts = resolve_choices(f, self.values)
                    if [v for _, v in opts] != getattr(sel, "_known", None):
                        keep = sel.value if any(v == sel.value for _, v in opts) else opts[0][1]
                        sel.set_options(opts)
                        sel.value = keep
                        sel._known = [v for _, v in opts]
            self._read()
            for f in self.action.fields:
                self.query_one(f"#row-{f.key}").display = bool(f.visible(self.values))
            argv = self.action.build(self.values)
            self.query_one("#preview", Static).update("$ " + shlex.join(argv))
            warn = self.action.danger(self.values)
            self.query_one("#warning", Static).update(("⚠  " + warn) if warn else "")
        finally:
            self._building = False

    def on_select_changed(self, event: Select.Changed) -> None:
        self._refresh()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._refresh()

    def _visible_missing(self) -> Optional[str]:
        for f in self.action.fields:
            if f.kind == "input" and f.visible(self.values) and not str(self.values.get(f.key, "")).strip():
                return f.label
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss(None)
            return
        self._read()
        missing = self._visible_missing()
        if missing:
            self.query_one("#warning", Static).update(f"⚠  Please fill in: {missing}")
            return
        argv = self.action.build(self.values)
        warn = self.action.danger(self.values)
        if warn:
            def after_confirm(ok: Optional[bool]) -> None:
                if ok:
                    self.dismiss(argv)  # do not return the awaitable from a screen callback

            self.app.push_screen(ConfirmScreen(warn, shlex.join(argv)), after_confirm)
        else:
            self.dismiss(argv)

    def action_cancel(self) -> None:
        self.dismiss(None)


class MenuApp(App):
    TITLE = "adam-seeker-metadata"
    SUB_TITLE = "pick an action, review the command, run it"
    BINDINGS = [Binding("q", "quit", "Quit")]
    CSS = """
    #left { width: 42; border-right: solid $primary; }
    #details { padding: 1 2; }
    """

    def __init__(self, runner: Callable[[List[str]], int] = default_runner):
        super().__init__()
        self.runner = runner
        self.last_command: Optional[List[str]] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield OptionList(*self._options(), id="left")
            yield Static("", id="details")
        yield Footer()

    def _options(self) -> List[Option]:
        out: List[Option] = []
        group = None
        for a in ACTIONS:
            if a.group != group:
                group = a.group
                out.append(Option(f"[b]{group}[/b]", disabled=True))
            out.append(Option("  " + a.label, id=a.id))
        return out

    def on_mount(self) -> None:
        ol = self.query_one("#left", OptionList)
        ol.focus()
        ol.highlighted = 1
        self._show_details(ACTIONS[0])

    def _action(self, option_id: Optional[str]) -> Optional[Action]:
        return next((a for a in ACTIONS if a.id == option_id), None)

    def _show_details(self, a: Action) -> None:
        self.query_one("#details", Static).update(f"[b]{a.label}[/b]\n\n{a.description}\n\n[dim]Enter to choose options[/dim]")

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        a = self._action(event.option.id)
        if a:
            self._show_details(a)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        a = self._action(event.option.id)
        if a:
            self.push_screen(FormScreen(a), self._after_form)

    def _after_form(self, argv: Optional[List[str]]) -> None:
        if not argv:
            return
        self.last_command = argv
        with self.suspend():
            self.runner(argv)


def main() -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("The menu needs an interactive terminal.")
        return 1
    MenuApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
