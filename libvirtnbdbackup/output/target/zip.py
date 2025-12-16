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
import fnmatch
import zipfile
import logging
import time
from argparse import Namespace
from typing import IO, Tuple, Optional
from libvirtnbdbackup.output import exceptions
from libvirtnbdbackup.output.base import TargetPlugin


log = logging.getLogger("zip")


class zip(TargetPlugin):
    """Backup to zip file"""

    def __init__(self, args: Optional[Namespace]) -> None:
        self.zipStream: zipfile.ZipFile
        self.zipFileStream: IO[bytes]

    def create(self, targetDir) -> None:
        try:
            # pylint: disable=consider-using-with
            self.zipStream = zipfile.ZipFile("test.zip", "a", zipfile.ZIP_STORED)
        except zipfile.error as e:
            raise exceptions.OutputOpenException(f"Failed to open zip file: {e}") from e

    def open(self, targetFile: str, mode="w") -> IO[bytes]:
        """Open wrapper"""
        if mode == "w":
            file = zipfile.ZipInfo(
                filename=targetFile,
            )

            dateTime: time.struct_time = time.localtime(time.time())
            timeStamp: Tuple[int, int, int, int, int, int] = (
                dateTime.tm_year,
                dateTime.tm_mon,
                dateTime.tm_mday,
                dateTime.tm_hour,
                dateTime.tm_min,
                dateTime.tm_sec,
            )
            file.date_time = timeStamp
            file.compress_type = zipfile.ZIP_STORED
        elif mode == "r":
            file = targetFile

        try:
            # pylint: disable=consider-using-with
            self.zipFileStream = self.zipStream.open(file, mode, force_zip64=True)
            return self.zipFileStream
        except zipfile.error as e:
            raise exceptions.OutputOpenException(
                f"Failed to open zip stream: {e}"
            ) from e

        return False

    def truncate(self, size: int) -> None:
        """Truncate target file"""
        raise RuntimeError("Not implemented")

    def write(self, data: bytes) -> int:
        """Write wrapper"""
        return self.zipFileStream.write(data)

    def read(self, dlen: int) -> int:
        """Write wrapper"""
        return

    def close(self) -> None:
        """Close wrapper"""
        log.debug("Close file")
        self.zipFileStream.close()

    def checksum(self) -> None:
        """Checksum: not implemented for zip file"""
        return

    def rename(self, targetFilePartial: str, targetFile: str) -> None:
        """rename"""
        return

    def exists(self, args: Namespace, fileName: str):
        """Check if file exists"""
        for file in self.zipStream.namelist():
            if fnmatch.fnmatch(file, fileName):
                return True
        return False
