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
import logging
import builtins
from typing import IO, Union, Any
from libvirtnbdbackup.output import exceptions

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

log = logging.getLogger("directory")


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
        mode: Union[Literal["w"], Literal["wb"], Literal["rb"], Literal["r"]] = "wb",
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

    def write(self, data: bytes) -> int:
        """Write wrapper"""
        self.chksum = zlib.adler32(data, self.chksum)
        written = self.fileHandle.write(data)
        assert written == len(data)
        return written

    def read(self, size=-1) -> int:
        """Read wrapper"""
        return self.fileHandle.read(size)

    def flush(self) -> None:
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

    def close(self) -> None:
        """Close wrapper"""
        log.debug("Close file")
        self.fileHandle.close()

    def seek(self, tgt: int, whence: int = 0) -> int:
        """Seek wrapper"""
        return self.fileHandle.seek(tgt, whence)

    def checksum(self) -> int:
        """Return computed checksum"""
        cur = self.chksum
        self.chksum = 1
        return cur
