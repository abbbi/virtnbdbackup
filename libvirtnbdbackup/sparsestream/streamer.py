"""
    Copyright (C) 2023  Michael Ablassmeier <abi@grinser.de>
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
import json
import os
import datetime

from libvirtnbdbackup.sparsestream import exceptions


class SparseStream:

    """Sparse Stream writer/reader class"""

    def __init__(self, types, version=2):
        """Stream version:

        1: base version
        2: stream version with compression support
        """
        self.version = version
        self.compressionMethod = "lz4"
        self.types = types.SparseStreamTypes()

    def dumpMetadata(
        self,
        args,
        virtualSize,
        dataSize,
        disk,
    ):
        """First block in backup stream is Meta data information
        about virtual size of the disk being backed up, aswell
        as various information regarding backup.
        Dumps Metadata frame to be written at start of stream in
        json format.
        """
        meta = {
            "virtualSize": virtualSize,
            "dataSize": dataSize,
            "date": datetime.datetime.now().isoformat(),
            "diskName": disk.target,
            "diskFormat": disk.format,
            "checkpointName": args.cpt.name,
            "compressed": args.compress,
            "compressionMethod": self.compressionMethod,
            "parentCheckpoint": args.cpt.parent,
            "incremental": (args.level in ("inc", "diff")),
            "streamVersion": self.version,
        }
        return json.dumps(meta, indent=4).encode("utf-8")

    def writeCompressionTrailer(self, writer, trailer):
        """Dump compression trailer to end of stream"""
        size = writer.write(json.dumps(trailer).encode())
        writer.write(self.types.TERM)
        self.writeFrame(writer, self.types.COMP, 0, size)

    def _readHeader(self, reader):
        """Attempt to read header"""
        header = reader.read(self.types.FRAME_LEN)
        try:
            kind, start, length = header.split(b" ", 2)
        except ValueError as err:
            raise exceptions.BlockFormatException(
                f"Invalid block format: [{err}]"
            ) from err

        return kind, start, length

    @staticmethod
    def _parseHeader(kind, start, length):
        """Return parsed header information"""
        try:
            return kind, int(start, 16), int(length, 16)
        except ValueError as err:
            raise exceptions.FrameformatException(
                f"Invalid frame format: [{err}]"
            ) from err

    def readCompressionTrailer(self, reader):
        """If compressed stream is found, information about compressed
        block sizes is appended as last json payload.

        Function seeks to end of file and reads trailer information.
        """
        pos = reader.tell()
        reader.seek(0, os.SEEK_END)
        reader.seek(-(self.types.FRAME_LEN + len(self.types.TERM)), os.SEEK_CUR)
        _, _, length = self._readHeader(reader)
        reader.seek(-(self.types.FRAME_LEN + int(length, 16)), os.SEEK_CUR)
        trailer = self.loadMetadata(reader.read(int(length, 16)))
        reader.seek(pos)
        return trailer

    @staticmethod
    def loadMetadata(s):
        """Load and parse metadata information
        Parameters:
            s:  (str)   Json string as received during data file read
        Returns:
            json.loads: (dict)  Decoded json string as python object
        """
        try:
            return json.loads(s.decode("utf-8"))
        except json.decoder.JSONDecodeError as err:
            raise exceptions.MetaHeaderFormatException(
                f"Invalid meta header format: [{err}]"
            ) from err

    def writeFrame(self, writer, kind, start, length):
        """Write backup frame
        Parameters:
            writer: (fh)    Writer object that implements .write()
        """
        writer.write(self.types.FRAME % (kind, start, length))

    def readFrame(self, reader):
        """Read backup frame
        Parameters:
            reader: (fh)    Reader object which implements .read()
        """
        kind, start, length = self._readHeader(reader)
        return self._parseHeader(kind, start, length)
