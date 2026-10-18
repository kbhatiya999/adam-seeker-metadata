import asyncio
import contextlib

from seeker_tui import app as tui  # noqa: E402
from textual.widgets import Button, Checkbox, Input, Select, Static  # noqa: E402


def action(action_id):
    return next(a for a in tui.ACTIONS if a.id == action_id)


def test_build_commands():
    a = action("update")
    assert a.build({"where": "gh"}) == ["mise", "run", "gh:videos:update"]
    assert a.danger({"where": "gh"}) and not a.danger({"where": "local"})
    assert action("rebuild").danger({"where": "local"})  # rebuild always warns
    assert action("method-set").build({"where": "act", "setting": "transcript", "value": "ytdlp"}) == \
        ["mise", "run", "act:method:set", "--", "transcript", "ytdlp"]
    assert action("transcripts").build({"cmd": "download-missing", "method": "ytdlp", "limit": "3"}) == \
        ["mise", "run", "local:transcripts:manage", "--", "--method", "ytdlp", "download-missing", "--limit", "3"]
    assert action("transcripts").build({"cmd": "compare", "video_id": "abc", "format": "ttml", "final": "srt,txt"}) == \
        ["mise", "run", "local:transcripts:manage", "--", "--format", "ttml", "--final", "srt,txt", "compare", "abc"]
    assert action("method-show").build({"where": "all"}) == ["mise", "run", "all:method:show"]
    assert action("dashboard").build({"what": "local:tilt:up"}) == ["mise", "run", "local:tilt:up"]
    assert action("process").build({"strategy": "english-notes", "videos": " a,b ", "max_requests": ""}) == \
        ["mise", "run", "local:knowledge:manage", "--", "process", "--strategy", "english-notes", "--videos", "a,b"]
    assert action("evaluate").build({"processing": "chunks", "chat": "multilingual", "videos": "", "judge": False}) == \
        ["mise", "run", "local:eval:manage", "--", "run", "--processing", "chunks", "--chat", "multilingual", "--no-judge"]
    assert action("ask").build({"question": "q?", "processing": "chunks", "chat": "keyword"}) == \
        ["mise", "run", "local:chat:ask", "--", "q?", "--processing", "chunks", "--chat", "keyword"]
    assert ("english-notes", "english-notes") in tui.plugin_choices(tui.plugins.PROCESSING_STRATEGIES)
    t = action("transcripts").build
    assert t({"cmd": "download-missing", "method": "", "limit": "5", "max_attempts": "9", "keep_source": True}) == \
        ["mise", "run", "local:transcripts:manage", "--", "--keep-source", "download-missing", "--limit", "5", "--max-attempts", "9"]
    assert t({"cmd": "list-missing", "list_limit": "40"}) == ["mise", "run", "local:transcripts:manage", "--", "list-missing", "--limit", "40"]
    assert action("manage").build({"cmd": "categorize", "video_id": "v", "categories": "a", "relevance": "7", "notes": "n"}) == \
        ["mise", "run", "local:videos:manage", "--", "categorize", "v", "--categories", "a", "--relevance", "7", "--notes", "n"]
    assert action("manage").build({"cmd": "priority", "video_id": "v", "category": "c", "priority_relevance": ""}) == \
        ["mise", "run", "local:videos:manage", "--", "priority", "v", "--category", "c"]
    assert action("process").build({"strategy": "chunks", "force": True, "provider": "queue", "max_requests": "2"}) == \
        ["mise", "run", "local:knowledge:manage", "--", "process", "--strategy", "chunks", "--force", "--provider", "queue", "--max-requests", "2"]
    assert action("llm-queue").build({"what": "pending", "tool": "judge", "limit": ""}) == \
        ["mise", "run", "local:llm:manage", "--", "pending", "--tool", "judge"]
    assert action("eval-info").build({"what": "questions", "videos": "a,b"}) == \
        ["mise", "run", "local:eval:manage", "--", "questions", "--videos", "a,b"]
    assert action("sdk-new").build({"name": "rag", "plugin": ""}) == ["mise", "run", "sdk:new", "--", "rag"]
    assert action("profile-use").build({"methods": "ytdlp", "model": "gemini-lite"}) == \
        ["mise", "run", "local:profile:use", "--", "ytdlp", "gemini-lite"]
    assert action("profile-use").build({"methods": "none", "model": "none"}) == ["mise", "run", "local:profile:use"]
    assert action("dashboard").build({"what": "local:workspace:graph"}) == ["mise", "run", "local:workspace:graph"]
    assert action("nuke").build({"dry": True, "all": True, "yes": False}) == \
        ["mise", "run", "nuke", "--", "--dry-run", "--all"]
    assert action("nuke").danger({"dry": False, "yes": True}) and not action("nuke").danger({"dry": True, "yes": True})


def make_app(calls):
    class App(tui.MenuApp):
        def suspend(self):  # no real terminal under test
            return contextlib.nullcontext()

    return App(runner=lambda argv: calls.append(argv) or 0)


def run(coro):
    asyncio.run(coro)


def test_run_local_update_without_confirmation():
    calls = []

    async def go():
        app = make_app(calls)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.press("enter")  # first action: Update videos
            await pilot.pause()
            assert isinstance(app.screen, tui.FormScreen)
            assert "$ mise run local:videos:update" in str(app.screen.query_one("#preview", Static).render())
            app.screen.query_one("#run", Button).press()
            await pilot.pause()

    run(go())
    assert calls == [["mise", "run", "local:videos:update"]]


def test_gh_requires_confirmation():
    calls = []

    async def go():
        app = make_app(calls)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.press("enter")
            await pilot.pause()
            app.screen.query_one("#f-where", Select).value = "gh"
            await pilot.pause()
            assert "REAL workflow" in str(app.screen.query_one("#warning", Static).render())
            app.screen.query_one("#run", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, tui.ConfirmScreen)
            await pilot.press("n")  # cancel: nothing runs
            await pilot.pause()
            assert calls == []
            app.screen.query_one("#run", Button).press()
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()

    run(go())
    assert calls == [["mise", "run", "gh:videos:update"]]


def test_method_values_follow_setting_and_required_input():
    calls = []

    async def go():
        app = make_app(calls)
        async with app.run_test(size=(120, 60)) as pilot:
            ol = app.query_one("#left")
            idx = next(i for i in range(ol.option_count) if ol.get_option_at_index(i).id == "method-set")
            ol.highlighted = idx
            await pilot.press("enter")
            await pilot.pause()
            form = app.screen
            form.query_one("#f-setting", Select).value = "transcript"
            await pilot.pause()
            values = [v for v in (form.query_one("#f-value", Select)._options)]
            assert ("youtube_transcript_api", "youtube_transcript_api") in [(p, v) for p, v in values]
            form.query_one("#f-value", Select).value = "youtube_transcript_api"
            await pilot.pause()
            assert "local:method:set -- transcript youtube_transcript_api" in str(form.query_one("#preview", Static).render())
            app.screen.query_one("#run", Button).press()
            await pilot.pause()

    run(go())
    assert calls == [["mise", "run", "local:method:set", "--", "transcript", "youtube_transcript_api"]]


def test_missing_required_input_blocks_run():
    calls = []

    async def go():
        app = make_app(calls)
        async with app.run_test(size=(120, 60)) as pilot:
            ol = app.query_one("#left")
            idx = next(i for i in range(ol.option_count) if ol.get_option_at_index(i).id == "transcripts")
            ol.highlighted = idx
            await pilot.press("enter")
            await pilot.pause()
            app.screen.query_one("#f-cmd", Select).value = "download"
            await pilot.pause()
            app.screen.query_one("#run", Button).press()  # video id empty
            await pilot.pause()
            assert isinstance(app.screen, tui.FormScreen)
            assert "Please fill in" in str(app.screen.query_one("#warning", Static).render())
            app.screen.query_one("#f-video_id", Input).value = "abc123"
            await pilot.pause()
            app.screen.query_one("#run", Button).press()
            await pilot.pause()

    run(go())
    # the method defaults to the saved TRANSCRIPT_METHOD, so no --method is passed
    assert calls == [["mise", "run", "local:transcripts:manage", "--", "--format", "ttml", "--final", "srt,txt", "download", "abc123"]]


def test_nuke_dry_run_default_no_confirmation_but_real_yes_confirms():
    calls = []

    async def go():
        app = make_app(calls)
        async with app.run_test(size=(120, 60)) as pilot:
            ol = app.query_one("#left")
            idx = next(i for i in range(ol.option_count) if ol.get_option_at_index(i).id == "nuke")
            ol.highlighted = idx
            await pilot.press("enter")
            await pilot.pause()
            assert "--dry-run" in str(app.screen.query_one("#preview", Static).render())
            app.screen.query_one("#run", Button).press()
            await pilot.pause()
            assert calls == [["mise", "run", "nuke", "--", "--dry-run"]]
            await pilot.press("enter")  # reopen form for the same highlighted action
            await pilot.pause()
            app.screen.query_one("#f-dry", Checkbox).value = False
            app.screen.query_one("#f-yes", Checkbox).value = True
            await pilot.pause()
            app.screen.query_one("#run", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, tui.ConfirmScreen)
            await pilot.press("n")
            await pilot.pause()

    run(go())
    assert calls == [["mise", "run", "nuke", "--", "--dry-run"]]
