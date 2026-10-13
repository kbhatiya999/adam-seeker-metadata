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
    assert calls == [["mise", "run", "local:transcripts:manage", "--", "--method", "youtube_transcript_api", "--format", "ttml", "--final", "srt,txt", "download", "abc123"]]


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
