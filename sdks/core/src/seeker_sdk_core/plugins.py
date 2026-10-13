"""Plugin registry based on Python entry points.

A package adds a plugin by declaring it in its own pyproject.toml, for example::

    [project.entry-points."seeker.video_sources"]
    my_source = "my_package.sources:MySource"

Nothing in the existing SDKs has to change. Plugins can also be registered in-process
(`register`), which is what tests and notebooks use.
"""

import logging
from collections import defaultdict
from importlib.metadata import entry_points
from typing import Any, Dict, List

from .errors import PluginError

VIDEO_SOURCES = "seeker.video_sources"
TRANSCRIPT_METHODS = "seeker.transcript_methods"

logger = logging.getLogger(__name__)
_registered: Dict[str, Dict[str, Any]] = defaultdict(dict)


def register(group: str, name: str, plugin: Any) -> None:
    """Register a plugin in this process (takes precedence over entry points of the same name)."""
    _registered[group][name] = plugin


def unregister(group: str, name: str) -> None:
    _registered[group].pop(name, None)


def names(group: str) -> List[str]:
    """Names of all plugins in a group (entry points and in-process registrations)."""
    found = {ep.name for ep in entry_points(group=group)}
    return sorted(found | set(_registered[group]))


def load(group: str, name: str) -> Any:
    """Return the plugin object registered under `name` in `group`."""
    if name in _registered[group]:
        return _registered[group][name]
    for ep in entry_points(group=group):
        if ep.name == name:
            try:
                return ep.load()
            except Exception as e:  # a broken plugin must not look like a missing one
                raise PluginError(f"plugin {name!r} in {group!r} failed to load: {e}") from e
    raise PluginError(f"no plugin {name!r} in {group!r}; available: {', '.join(names(group)) or 'none'}")


def describe(group: str) -> Dict[str, str]:
    """name -> where it comes from, for listing."""
    out = {ep.name: f"{ep.dist.name if ep.dist else '?'}: {ep.value}" for ep in entry_points(group=group)}
    for name in _registered[group]:
        out[name] = "registered in-process"
    return dict(sorted(out.items()))
