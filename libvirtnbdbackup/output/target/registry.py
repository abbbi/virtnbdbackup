"""Registry and entry-point discovery for output target plugins."""

from typing import Dict, List, Type

import pkg_resources

from libvirtnbdbackup.output import exceptions
from libvirtnbdbackup.output.target.base import OutputTarget

ENTRY_POINT_GROUP = "virtnbdbackup.output_targets"

_plugins: Dict[str, Type[OutputTarget]] = {}
_entry_points_loaded = False


def register(name: str, plugin: Type[OutputTarget]) -> None:
    """Register an output target plugin under a unique name."""
    if not name:
        raise exceptions.OutputPluginException("Output target name must not be empty")
    if not isinstance(plugin, type) or not issubclass(plugin, OutputTarget):
        raise exceptions.OutputPluginException(
            f"Output target plugin [{name}] must inherit from OutputTarget"
        )
    if name in _plugins and _plugins[name] is not plugin:
        raise exceptions.OutputPluginException(
            f"Output target plugin [{name}] is already registered"
        )
    _plugins[name] = plugin


def discover() -> None:
    """Load output target plugins exposed by installed distributions."""
    global _entry_points_loaded  # pylint: disable=global-statement
    if _entry_points_loaded:
        return
    _entry_points_loaded = True
    for entryPoint in pkg_resources.iter_entry_points(ENTRY_POINT_GROUP):
        try:
            register(entryPoint.name, entryPoint.load())
        except Exception as e:
            raise exceptions.OutputPluginException(
                f"Failed to load output target plugin [{entryPoint.name}]: {e}"
            ) from e


def create(name: str, **kwargs) -> OutputTarget:
    """Create a registered output target plugin instance."""
    discover()
    try:
        plugin = _plugins[name]
    except KeyError as e:
        targets = ", ".join(sorted(_plugins)) or "none"
        raise exceptions.OutputPluginException(
            f"Unknown output target plugin [{name}], available plugins: {targets}"
        ) from e
    return plugin(**kwargs)


def names() -> List[str]:
    """Return all available output target plugin names."""
    discover()
    return sorted(_plugins)
