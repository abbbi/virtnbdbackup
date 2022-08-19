"""
    Copyright (C) 2021  Michael Ablassmeier <abi@grinser.de>
    Copyright (C) 2020 Red Hat, Inc.

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

from dataclasses import dataclass


@dataclass(frozen=True)
class SparseStreamTypes:
    # pylint: disable=too-many-instance-attributes
    """Sparse stream format

    Extended format based on the examples provided by the
    ovirt-imageio project:

    https://github.com/oVirt/ovirt-imageio/tree/master/examples

    META:   start of meta information header
    DATA:   data block marker
    ZERO:   zero block marker
    STOP:   stop block marker
    TERM:   termination identifier
    FRAME:  assembled frame
    FRAME_LEN: length of frame

    Stream format
    =============

    Stream is composed of one of more frames.

    Meta frame
    ----------
    Stream metadata, must be the first frame.

    "meta" space start length "\r\n" <json-payload> \r\n

    Metadata keys in the json payload:

    - virtual-size: image virtual size in bytes
    - data-size: number of bytes in data frames
    - date: ISO 8601 date string

    Data frame
    ----------
    The header is followed by length bytes and terminator.
    "data" space start length "\r\n" <length bytes> "\r\n"

    Zero frame
    ----------
    A zero extent, no payload.
    "zero" space start length "\r\n"

    Stop frame
    ----------
    Marks the end of the stream, no payload.
    "stop" space start length "\r\n"

    Regular stream Example
    -------
    meta 0000000000000000 0000000000000083\r\n
    {
        [.]]
    }\r\n
    data 0000000000000000 00000000000100000\r\n
    <1 MiB bytes>\r\n
    zero 0000000000100000 00000000040000000\r\n
    data 0000000040100000 00000000000001000\r\n
    <4096 bytes>\r\n
    stop 0000000000000000 00000000000000000\r\n


    Compressed stream:
    -------
    Ends with compression marker:
    stop 0000000000000000 00000000000000000\r\n
    <json payload with compressed block sizes>\r\n
    comp 0000000000000000 00000000000000010\r\n
    """

    META: bytes = b"meta"
    DATA: bytes = b"data"
    COMP: bytes = b"comp"
    ZERO: bytes = b"zero"
    STOP: bytes = b"stop"
    TERM: bytes = b"\r\n"
    FRAME: bytes = b"%s %016x %016x" + TERM
    FRAME_LEN: int = len(FRAME % (STOP, 0, 0))
