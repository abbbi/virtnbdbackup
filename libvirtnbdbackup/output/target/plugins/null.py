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
from typing import IO, Any
from libvirtnbdbackup.output.target.directory import Directory


log = logging.getLogger("Null")


class Null(Directory):
    """Simulate write data without actually storing anything, for testing
    backup operation without causing I/O"""

    supports_input = True
    supported_backup_modes = ["full"]

    def open(self, targetFile: str, mode: str = "wb") -> IO[Any]:
        log.info("Will write data to the void ..")
        return super().open(targetFile, mode)

    def write(self, data: bytes) -> int:
        """Return only len of bytes without writing"""
        return len(data)
