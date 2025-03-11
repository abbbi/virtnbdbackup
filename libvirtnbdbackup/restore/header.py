#!/usr/bin/python3
"""
Copyright (C) 2023 Michael Ablassmeier <abi@grinser.de>

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
from typing import Dict
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.sparsestream import streamer
from libvirtnbdbackup.sparsestream.exceptions import StreamFormatException
from libvirtnbdbackup.exceptions import RestoreError
from libvirtnbdbackup.output.exceptions import OutputException


def get(diskFile: str, stream: streamer.SparseStream) -> Dict[str, str]:
    """Read header from data file"""
    try:
        return lib.dumpMetaData(diskFile, stream)
    except StreamFormatException as errmsg:
        raise RestoreError(
            f"Reading metadata from [{diskFile}] failed: [{errmsg}]"
        ) from errmsg
    except OutputException as errmsg:
        raise RestoreError(
            f"Reading data file [{diskFile}] failed: [{errmsg}]"
        ) from errmsg
