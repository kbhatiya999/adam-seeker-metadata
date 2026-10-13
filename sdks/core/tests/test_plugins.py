import pytest

from seeker_sdk_core import PluginError, plugins


def test_register_load_and_unregister():
    plugins.register("test.group", "mine", object)
    assert plugins.load("test.group", "mine") is object
    assert "mine" in plugins.names("test.group")
    assert plugins.describe("test.group")["mine"] == "registered in-process"
    plugins.unregister("test.group", "mine")
    with pytest.raises(PluginError, match="no plugin 'mine'"):
        plugins.load("test.group", "mine")


def test_entry_points_of_the_installed_sdks_are_discovered():
    assert {"youtube_api", "ytdlp"} <= set(plugins.names(plugins.VIDEO_SOURCES))
    assert {"ytdlp", "youtube_transcript_api"} <= set(plugins.names(plugins.TRANSCRIPT_METHODS))
    assert plugins.describe(plugins.VIDEO_SOURCES)["ytdlp"].startswith("seeker-sdk-videos:")


def test_unknown_plugin_lists_the_available_ones():
    with pytest.raises(PluginError, match="available: .*ytdlp"):
        plugins.load(plugins.VIDEO_SOURCES, "does-not-exist")
