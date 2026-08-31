"""
Copyright (C) 2026  Michael Ablassmeier <abi@grinser.de>

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
import os
import sys
import time
import zipfile
from typing import IO, Any, Optional, Tuple

from libvirtnbdbackup.output import exceptions
from libvirtnbdbackup.output.target.base import OutputTarget
from libvirtnbdbackup.output.target.plugins.directory import Directory

log = logging.getLogger("zip")


class Zip(OutputTarget):
    """Write backup files to an uncompressed ZIP stream."""

    def __init__(self, output: Optional[IO[bytes]] = None) -> None:
        self.zipStream: zipfile.ZipFile
        self.zipFileStream: IO[bytes]

        log.info("Writing zip file stream to stdout")
        if output is None:
            output = sys.stdout.buffer
        try:
            # pylint: disable=consider-using-with
            self.zipStream = zipfile.ZipFile(output, "x", zipfile.ZIP_STORED)
        except (OSError, zipfile.error) as e:
            raise exceptions.OutputOpenException(f"Failed to open zip file: {e}") from e

    def create(self, targetDir: str) -> None:
        """Create directories used for temporary backup metadata."""
        Directory().create(targetDir)

    def open(self, targetFile: str, mode: str = "w") -> IO[Any]:
        """Open a new file in the ZIP stream."""
        if mode not in ("w", "wb"):
            raise exceptions.OutputOpenException(
                f"ZIP output target does not support mode [{mode}]"
            )
        zipFile = zipfile.ZipInfo(filename=os.path.basename(targetFile))
        dateTime: time.struct_time = time.localtime(time.time())
        timeStamp: Tuple[int, int, int, int, int, int] = (
            dateTime.tm_year,
            dateTime.tm_mon,
            dateTime.tm_mday,
            dateTime.tm_hour,
            dateTime.tm_min,
            dateTime.tm_sec,
        )
        zipFile.date_time = timeStamp
        zipFile.compress_type = zipfile.ZIP_STORED

        try:
            # pylint: disable=consider-using-with
            self.zipFileStream = self.zipStream.open(zipFile, "w", force_zip64=True)
            return self.zipFileStream
        except (OSError, zipfile.error) as e:
            raise exceptions.OutputOpenException(
                f"Failed to open zip stream: {e}"
            ) from e

    def truncate(self, size: int) -> None:
        """ZIP members cannot be truncated."""
        raise RuntimeError("Not implemented")

    def write(self, data: bytes) -> int:
        """Write to the current ZIP member."""
        return self.zipFileStream.write(data)

    def close(self) -> None:
        """Close the current ZIP member."""
        log.debug("Close file")
        self.zipFileStream.close()

    def checksum(self) -> None:
        """ZIP output does not use sidecar checksums."""
        return None

    def add_file(self, source: str, target: Optional[str] = None) -> None:
        """Add an existing file to the ZIP archive."""
        self.zipStream.write(source, target)

    def add_tree(self, source: str) -> None:
        """Add an existing directory tree to the ZIP archive."""
        for dirname, _, files in os.walk(source):
            self.zipStream.write(dirname)
            for filename in files:
                path = os.path.join(dirname, filename)
                self.zipStream.write(path)

    def finish(self) -> None:
        """Write the ZIP central directory and close the archive."""
        self.zipStream.close()
