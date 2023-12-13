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
import os
from typing import List
from argparse import Namespace
from libvirtnbdbackup import virt
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.restore import header
from libvirtnbdbackup.restore import server
from libvirtnbdbackup.restore import image
from libvirtnbdbackup.restore import data
from libvirtnbdbackup.sparsestream import types
from libvirtnbdbackup.sparsestream import streamer
from libvirtnbdbackup.exceptions import RestoreError


def restore(args: Namespace, dataFiles: List[str], virtClient: virt.client) -> bool:
    """Reconstruct image from a given set of data files"""
    stream = streamer.SparseStream(types)

    result: bool = False

    sourceFile = os.path.join(args.input, dataFiles[-1])
    meta = header.get(sourceFile, stream)
    if not meta:
        return result

    diskName = meta["diskName"]
    targetFile = os.path.join(args.output, diskName)
    if lib.exists(args, targetFile):
        raise RestoreError(f"Targetfile {targetFile} already exists.")

    try:
        image.create(args, meta, targetFile, args.sshClient)
    except RestoreError as errmsg:
        raise errmsg

    connection = server.start(args, diskName, targetFile, virtClient)

    for disk in dataFiles:
        sourceFile = os.path.join(args.input, disk)
        result = data.restore(args, stream, sourceFile, targetFile, connection)

    connection.disconnect()

    return result
