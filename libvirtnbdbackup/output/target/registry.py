"""
Copyright (C) 2026  Michael Ablassmeier <abi@grinser.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import importlib
from typing import Any, Dict, Iterable, List, Type

from libvirtnbdbackup.output import exceptions
from libvirtnbdbackup.output.target.base import OutputTarget

ENTRY_POINT_GROUP = "virtnbdbackup.output_targets"

_plugins: Dict[str, Type[OutputTarget]] = {}
_entry_points_loaded = False


def _entryPoints() -> Iterable[Any]:
    """Return compatible entry points on both current and older Python."""
    try:
        metadata = importlib.import_module("importlib.metadata")
    except ImportError:  # pragma: no cover - Python 3.7 and older
        resources = importlib.import_module("pkg_resources")
        return resources.iter_entry_points(ENTRY_POINT_GROUP)

    try:
        return metadata.entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover - Python 3.8 and 3.9
        discovered = metadata.entry_points()
        return discovered.get(ENTRY_POINT_GROUP, ())


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
    for entryPoint in _entryPoints():
        try:
            register(entryPoint.name, entryPoint.load())
        except Exception as e:
            raise exceptions.OutputPluginException(
                f"Failed to load output target plugin [{entryPoint.name}]: {e}"
            ) from e


def _get(name: str) -> Type[OutputTarget]:
    """Return a registered output target plugin class."""
    discover()
    try:
        return _plugins[name]
    except KeyError as e:
        targets = ", ".join(sorted(_plugins)) or "none"
        raise exceptions.OutputPluginException(
            f"Unknown output target plugin [{name}], available plugins: {targets}"
        ) from e


def create(name: str, **kwargs) -> OutputTarget:
    """Create a registered output target plugin instance."""
    return _get(name)(**kwargs)


def create_input(name: str, **kwargs) -> OutputTarget:
    """Create a plugin after verifying that it supports restore input."""
    plugin = _get(name)
    if not plugin.supports_input:
        raise exceptions.OutputPluginException(
            f"Plugin [{name}] does not support restore input"
        )
    return plugin(**kwargs)


def names() -> List[str]:
    """Return all available output target plugin names."""
    discover()
    return sorted(_plugins)
