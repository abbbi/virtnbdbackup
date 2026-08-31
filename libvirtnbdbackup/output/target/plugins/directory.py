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

import builtins
import glob
import logging
import os
import pprint
import shutil
import zlib
from typing import IO, Any, List, Optional

from libvirtnbdbackup.output import exceptions
from libvirtnbdbackup.output.target.base import OutputTarget

log = logging.getLogger("directory")


class Directory(OutputTarget):
    """Write backup files to a target directory."""

    supports_input = True

    def __init__(self) -> None:
        self.fileHandle: IO[Any]
        self.chksum: int = 1

    def create(self, targetDir: str) -> None:
        """Create a target directory."""
        log.debug("Create: %s", targetDir)
        if os.path.exists(targetDir):
            if not os.path.isdir(targetDir):
                raise exceptions.OutputCreateDirectory(
                    "Specified target is a file, not a directory"
                )
            return
        try:
            os.makedirs(targetDir)
        except OSError as e:
            raise exceptions.OutputCreateDirectory(
                f"Failed to create target directory: [{e}]"
            ) from e

    def open(self, targetFile: str, mode: str = "wb") -> IO[Any]:
        """Open a target file."""
        try:
            # pylint: disable=unspecified-encoding,consider-using-with
            self.fileHandle = builtins.open(targetFile, mode)
            return self.fileHandle
        except OSError as e:
            raise exceptions.OutputOpenException(
                f"Opening target file [{targetFile}] failed: {e}"
            ) from e

    def write(self, data: bytes) -> int:
        """Write bytes and update the checksum."""
        self.chksum = zlib.adler32(data, self.chksum)
        written = self.fileHandle.write(data)
        assert written == len(data)
        return written

    def read(self, size: int = -1) -> Any:
        """Read from the current target file."""
        return self.fileHandle.read(size)

    def flush(self) -> None:
        """Flush the current target file."""
        self.fileHandle.flush()

    def truncate(self, size: int) -> None:
        """Truncate the current target file."""
        try:
            self.fileHandle.truncate(size)
            self.fileHandle.seek(0)
        except OSError as e:
            raise exceptions.OutputException(
                f"Failed to truncate target file: [{e}]"
            ) from e

    def close(self) -> None:
        """Close the current target file."""
        log.debug("Close file")
        self.fileHandle.close()

    def seek(self, tgt: int, whence: int = 0) -> int:
        """Seek in the current target file."""
        return self.fileHandle.seek(tgt, whence)

    def checksum(self) -> int:
        """Return and reset the computed checksum."""
        current = self.chksum
        self.chksum = 1
        return current

    def add_file(self, source: str, target: Optional[str] = None) -> None:
        """Copy an existing file into the directory target."""
        if target is None:
            raise exceptions.OutputException("Directory target path is required")
        try:
            shutil.copyfile(source, target)
        except OSError as e:
            raise exceptions.OutputException(
                f"Failed to copy [{source}] to [{target}]: [{e}]"
            ) from e

    def exists(self, path: str) -> bool:
        """Return whether a filesystem input path exists."""
        return os.path.exists(path)

    def list(self, path: str, pattern: str, key: Optional[int] = None) -> List[str]:
        """List filesystem input paths matching a pattern by modification time."""
        files = glob.glob(os.path.join(path, pattern))
        files.sort(key=os.path.getmtime)
        if key is not None:
            try:
                files = [files[key]]
            except IndexError:
                files = []
        log.debug("Sorted data files: \n%s", pprint.pformat(files))
        return files
