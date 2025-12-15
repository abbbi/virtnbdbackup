"""
Copyright (C) 2025  Michael Ablassmeier <abi@grinser.de>

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

import pkgutil
import importlib
import inspect
from argparse import Namespace
from typing import Dict, Type

from libvirtnbdbackup.output import target
from libvirtnbdbackup.output.base import TargetPlugin
from libvirtnbdbackup.output.exceptions import OutputException


def loadPlugins() -> Dict[str, Type[TargetPlugin]]:
    """Load available output plugins"""
    plugins = {}

    for _, module_name, _ in pkgutil.iter_modules(target.__path__):
        module = importlib.import_module(f"{target.__name__}.{module_name}")
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, TargetPlugin) and obj is not TargetPlugin:
                plugins[name] = obj

    return plugins


def get(args: Namespace) -> TargetPlugin:
    """Get an instance of the appropriate plugin class."""
    plugins = loadPlugins()

    if ":" in args.output:
        load = args.output.split(":", 1)[0]
        pluginClass = plugins.get(load)
    else:
        if not args.stdout:
            pluginClass = plugins.get("Directory")
        else:
            pluginClass = plugins.get("Zip")
            args.output = "./"
            args.worker = 1

    if pluginClass is None:
        raise OutputException(f"No suitable plugin found for target: [{args.output}]")

    return pluginClass()
