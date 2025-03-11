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

import logging
import lz4.frame

log = logging.getLogger()


def decompressFrame(data: bytes) -> bytes:
    """Decompress lz4 frame, print frame information"""
    frameInfo = lz4.frame.get_frame_info(data)
    log.debug("Compressed Frame: %s", frameInfo)
    return lz4.frame.decompress(data)


def compressFrame(data: bytes, level: int) -> bytes:
    """Compress block with to lz4 frame, checksums
    enabled for safety
    """
    return lz4.frame.compress(
        data,
        content_checksum=True,
        block_checksum=True,
        compression_level=level,
    )
