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

from typing import Generator, IO, Any, Union
from nbd import Error as nbdError
from libvirtnbdbackup import lz4
from libvirtnbdbackup.exceptions import BackupException


def step(offset: int, length: int, maxRequestSize: int) -> Generator:
    """Process block and ensure to not exceed the maximum request size
    from NBD server.

    If length parameter is dict, compression was enabled during
    backup, thus we cannot use the offsets and sizes for the
    original data, but must use the compressed offsets and sizes
    to read the correct lz4 frames from the stream.
    """
    blockOffset = offset
    if isinstance(length, dict):
        blockOffset = offset
        compressOffset = list(length.keys())[0]
        for part in length[compressOffset]:
            blockOffset += part
            yield part, blockOffset
    else:
        blockOffset = offset
        while blockOffset < offset + length:
            blocklen = min(offset + length - blockOffset, maxRequestSize)
            yield blocklen, blockOffset
            blockOffset += blocklen


def write(
    writer: IO[Any], block, nbdCon, btype: str, compress: Union[bool, int]
) -> int:
    """Write single block that does not exceed nbd maxRequestSize
    setting. In case compression is enabled, single blocks are
    compressed using lz4.
    """
    if btype == "raw":
        writer.seek(block.offset)

    try:
        data = nbdCon.nbd.pread(block.length, block.offset)
    except nbdError as e:
        raise BackupException(e) from e

    if compress is not False:
        data = lz4.compressFrame(data, compress)

    return writer.write(data)
