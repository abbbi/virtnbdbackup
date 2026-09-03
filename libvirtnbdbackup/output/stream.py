"""
Copyright (C) 2023  Michael Ablassmeier <abi@grinser.de>

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

from argparse import Namespace
from libvirtnbdbackup.output.target import OutputTarget, create
from libvirtnbdbackup.output.exceptions import OutputPluginException


def get(
    args: Namespace,
) -> OutputTarget:
    """Get filehandle for output files based on output
    mode"""
    pluginName = getattr(args, "output_target", None)
    if pluginName is None:
        pluginName = "zip" if args.stdout else "directory"

    fileStream = create(pluginName)

    if hasattr(fileStream, "supported_backup_modes"):
        if args.level not in fileStream.supported_backup_modes:
            raise OutputPluginException(
                f"The selected backup mode [{args.level}] is not supported by"
                f" the [{pluginName}] plugin."
                f" Supported modes are: {fileStream.supported_backup_modes}"
            )
    if args.stdout is True:
        args.output = "./"
        args.worker = 1

    return fileStream
