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
import json
from typing import List, Dict, Tuple, IO
from libvirtnbdbackup import common as lib
from libvirtnbdbackup import output
from libvirtnbdbackup.output.exceptions import OutputException
from libvirtnbdbackup.exceptions import RestoreError
from libvirtnbdbackup.sparsestream.exceptions import StreamFormatException


def _parse(stream, sTypes, reader) -> Tuple[List, Dict]:
    """Read block offsets from backup stream image"""
    try:
        kind, start, length = stream.readFrame(reader)
        meta = stream.loadMetadata(reader.read(length))
    except StreamFormatException as errmsg:
        logging.error("Unable to read metadata header: %s", errmsg)
        raise RestoreError from errmsg

    if lib.isCompressed(meta):
        logging.error("Mapping compressed images currently not supported.")
        raise RestoreError

    assert reader.read(len(sTypes.TERM)) == sTypes.TERM

    dataRanges: List = []
    count: int = 0
    while True:
        kind, start, length = stream.readFrame(reader)
        if kind == sTypes.STOP:
            dataRanges[-1]["nextBlockOffset"] = None
            break

        blockInfo = {}
        blockInfo["count"] = count
        blockInfo["offset"] = reader.tell()
        blockInfo["originalOffset"] = start
        blockInfo["nextOriginalOffset"] = start + length
        blockInfo["length"] = length
        blockInfo["data"] = kind == sTypes.DATA
        blockInfo["file"] = os.path.abspath(reader.name)
        blockInfo["inc"] = meta["incremental"]

        if kind == sTypes.DATA:
            reader.seek(length, os.SEEK_CUR)
            assert reader.read(len(sTypes.TERM)) == sTypes.TERM

        nextBlockOffset = reader.tell() + sTypes.FRAME_LEN
        blockInfo["nextBlockOffset"] = nextBlockOffset
        dataRanges.append(blockInfo)
        count += 1

    return dataRanges, meta


def get(args, stream, sTypes, dataFiles: List) -> List:
    """Get data ranges for each file specified"""
    dataRanges = []
    for dFile in dataFiles:
        try:
            reader = output.openfile(dFile, "rb")
        except OutputException as e:
            logging.error("[%s]: [%s]", dFile, e)
            raise RestoreError from e

        Range, meta = _parse(stream, sTypes, reader)
        if Range is False or meta is False:
            logging.error("Unable to read meta header from backup file.")
            raise RestoreError("Invalid header")
        dataRanges.extend(Range)

        if args.verbose is True:
            logging.info(json.dumps(dataRanges, indent=4))
        else:
            logging.info(
                "Parsed [%s] block offsets from file [%s]", len(dataRanges), dFile
            )
        reader.close()

    return dataRanges


def dump(tfile: IO, dataRanges: List) -> bool:
    """Dump block map to temporary file"""
    try:
        tfile.write(json.dumps(dataRanges, indent=4).encode())
        return True
    except OSError as e:
        logging.error("Unable to write blockmap file: %s", e)
        return False
