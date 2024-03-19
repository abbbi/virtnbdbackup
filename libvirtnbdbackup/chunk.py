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
from typing import List, Any, Tuple, IO, Union
from libvirtnbdbackup import block
from libvirtnbdbackup import lz4

# pylint: disable=too-many-arguments


def write(
    writer: IO[Any], blk, nbdCon, btype: str, compress: Union[bool, int], pbar
) -> Tuple[int, List[int]]:
    """During extent processing, consecutive blocks with
    the same type(data or zeroed) are unified into one big chunk.
    This helps to reduce requests to the NBD Server.

    But in cases where the block to be saved exceeds the maximum
    recommended request size (nbdClient.maxRequestSize), we
    need to split one big request into multiple not exceeding
    the limit

    If compression is enabled, function returns a list of
    offsets for the compressed frames, which is appended
    to the end of the stream.
    """
    wSize = 0
    cSizes = []
    for blocklen, blockOffset in block.step(
        blk.offset, blk.length, nbdCon.maxRequestSize
    ):
        if btype == "raw":
            writer.seek(blockOffset)

        data = nbdCon.nbd.pread(blocklen, blockOffset)

        if compress is not False:
            compressed = lz4.compressFrame(data, compress)
            wSize += writer.write(compressed)
            cSizes.append(len(compressed))
        else:
            wSize += writer.write(data)

        pbar.update(blocklen)

    return wSize, cSizes


def read(
    reader: IO[Any],
    offset: int,
    length: int,
    nbdCon,
    compression: bool,
    pbar,
) -> int:
    """Read data from reader and write to nbd connection

    If Compression is enabled function receives length information
    as dict, which contains the stream offsets for the compressed
    lz4 frames.

    Frames are read from the stream at the compressed size information
    (offset in the stream).

    After decompression, data is written back to original offset
    in the virtual machine disk image.

    If no compression is enabled, data is read from the regular
    data header at its position and written to nbd target
    directly.
    """
    wSize = 0
    for blocklen, blockOffset in block.step(offset, length, nbdCon.maxRequestSize):
        if compression is True:
            data = lz4.decompressFrame(reader.read(blocklen))
            nbdCon.nbd.pwrite(data, offset)
            offset += len(data)
            wSize += len(data)
        else:
            data = reader.read(blocklen)
            nbdCon.nbd.pwrite(data, blockOffset)
            wSize += len(data)

        pbar.update(wSize)

    return wSize
