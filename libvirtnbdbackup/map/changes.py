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
from typing import List, IO, Any
from time import sleep
from libvirtnbdbackup import common as lib
from libvirtnbdbackup import output


def wait(offset: int, replayDevice: IO[Any], timeout: int = 60) -> None:
    """Sometimes seeking the NBD device may not yet be possible after
    it has just been initialized. Wait until we can seek to the biggest
    offset without OS error before continuing"""
    for _ in range(timeout):
        try:
            replayDevice.seek(offset)
            return
        except OSError:
            sleep(1)
    raise output.exceptions.OutputException("Timeout during setting up device.")


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
        wait(blockListInc[-1]["originalOffset"], replayDevice)
        for extent in blockListInc:
            if args.noprogress:
                logging.info(
                    "Replaying offset [%s] from [%s] original offset [%s]",
                    extent["offset"],
                    extent["file"],
                    extent["originalOffset"],
                )
            with output.openfile(os.path.abspath(extent["file"]), "rb") as replaySrc:
                replaySrc.seek(extent["offset"])
                logging.debug(
                    "Seek [%s], to [%s], currently at: [%s]",
                    replayDevice.name,
                    extent["originalOffset"],
                    replayDevice.tell(),
                )
                replayDevice.seek(extent["originalOffset"])
                replayDevice.write(replaySrc.read(extent["length"]))
            replayDevice.seek(0)
            replayDevice.flush()
            progressBar.update(extent["length"])

    progressBar.close()
