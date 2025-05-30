#!/usr/bin/python3
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
import os
import logging
from argparse import Namespace
from typing import List
from libvirtnbdbackup import common as lib
from libvirtnbdbackup import output


def replay(dataRanges: List, args: Namespace) -> None:
    """Replay the changes from an incremental or differential
    backup file to the NBD device"""
    logging.info("Replaying changes from incremental backups")
    blockListInc = list(
        filter(
            lambda x: x["inc"] is True,
            dataRanges,
        )
    )
    dataSize = sum(extent["length"] for extent in blockListInc)
    progressBar = lib.progressBar(dataSize, "replaying..", args)
    with output.openfile(args.device, "wb") as replayDevice:
        for extent in blockListInc:
            if args.noprogress:
                logging.info(
                    "Replaying offset %s from %s", extent["offset"], extent["file"]
                )
            with output.openfile(os.path.abspath(extent["file"]), "rb") as replaySrc:
                replaySrc.seek(extent["offset"])
                replayDevice.seek(extent["originalOffset"])
                replayDevice.write(replaySrc.read(extent["length"]))
            replayDevice.seek(0)
            replayDevice.flush()
            progressBar.update(extent["length"])

    progressBar.close()
