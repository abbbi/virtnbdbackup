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
import sys
import zlib
import zipfile
import logging
import time
import builtins
from typing import IO, Union, Tuple, Any
from libvirtnbdbackup.output import exceptions

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

log = logging.getLogger("output")


class target:
    """Directs output stream to either regular directory or
    zipfile. If other formats are added class should be
    used as generic wrapper for open()/write()/close() functions.
    """

    class Directory:
        """Backup to target directory"""

        def __init__(self) -> None:
            self.fileHandle: IO[Any]
            self.chksum: int = 1

        def create(self, targetDir) -> None:
            """Create wrapper"""
            log.debug("Create: %s", targetDir)
            if os.path.exists(targetDir):
                if not os.path.isdir(targetDir):
                    raise exceptions.OutputCreateDirectory(
                        "Specified target is a file, not a directory"
                    )
            if not os.path.exists(targetDir):
                try:
                    os.makedirs(targetDir)
                except OSError as e:
                    raise exceptions.OutputCreateDirectory(
                        f"Failed to create target directory: [{e}]"
                    )

        def open(
            self,
            targetFile: str,
            mode: Union[
                Literal["w"], Literal["wb"], Literal["rb"], Literal["r"]
            ] = "wb",
        ) -> IO[Any]:
            """Open target file"""
            try:
                # pylint: disable=unspecified-encoding,consider-using-with
                self.fileHandle = builtins.open(targetFile, mode)
                return self.fileHandle
            except OSError as e:
                raise exceptions.OutputOpenException(
                    f"Opening target file [{targetFile}] failed: {e}"
                ) from e

        def write(self, data):
            """Write wrapper"""
            self.chksum = zlib.adler32(data, self.chksum)
            return self.fileHandle.write(data)

        def read(self, size=-1):
            """Read wrapper"""
            return self.fileHandle.read(size)

        def flush(self):
            """Flush wrapper"""
            return self.fileHandle.flush()

        def truncate(self, size: int) -> None:
            """Truncate target file"""
            try:
                self.fileHandle.truncate(size)
                self.fileHandle.seek(0)
            except OSError as e:
                raise exceptions.OutputException(
                    f"Failed to truncate target file: [{e}]"
                ) from e

        def close(self):
            """Close wrapper"""
            log.debug("Close file")
            return self.fileHandle.close()

        def seek(self, tgt: int, whence: int = 0):
            """Seek wrapper"""
            return self.fileHandle.seek(tgt, whence)

        def checksum(self):
            """Return computed checksum"""
            cur = self.chksum
            self.chksum = 1
            return cur

    class Zip:
        """Backup to zip file"""

        def __init__(self):
            self.zipStream: zipfile.ZipFile
            self.zipFileStream: IO[bytes]

            log.info("Writing zip file stream to stdout")
            try:
                # pylint: disable=consider-using-with
                self.zipStream = zipfile.ZipFile(
                    sys.stdout.buffer, "x", zipfile.ZIP_STORED
                )
            except zipfile.error as e:
                raise exceptions.OutputOpenException(
                    f"Failed to open zip file: {e}"
                ) from e

        def create(self, targetDir) -> None:
            """Create wrapper"""
            log.debug("Create: %s", targetDir)
            target.Directory().create(targetDir)

        def open(self, fileName: str, mode: Literal["w"] = "w") -> IO[bytes]:
            """Open wrapper"""
            zipFile = zipfile.ZipInfo(
                filename=os.path.basename(fileName),
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
            zipFile.date_time = timeStamp
            zipFile.compress_type = zipfile.ZIP_STORED

            try:
                # pylint: disable=consider-using-with
                self.zipFileStream = self.zipStream.open(
                    zipFile, mode, force_zip64=True
                )
                return self.zipFileStream
            except zipfile.error as e:
                raise exceptions.OutputOpenException(
                    f"Failed to open zip stream: {e}"
                ) from e

            return False

        def truncate(self, size: int) -> None:
            """Truncate target file"""
            raise RuntimeError("Not implemented")

        def write(self, data):
            """Write wrapper"""
            return self.zipFileStream.write(data)

        def close(self):
            """Close wrapper"""
            log.debug("Close file")
            return self.zipFileStream.close()

        def checksum(self):
            """Checksum: not implemented for zip file"""
            return
