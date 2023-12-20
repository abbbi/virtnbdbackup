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
from typing import List, Dict, Tuple
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.exceptions import RestoreError
from libvirtnbdbackup.sparsestream.exceptions import StreamFormatException


def get(stream, sTypes, reader) -> Tuple[List, Dict]:
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
    while True:
        kind, start, length = stream.readFrame(reader)
        if kind == sTypes.STOP:
            dataRanges[-1]["nextBlockOffset"] = None
            break

        blockInfo = {}
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

    return dataRanges, meta
