#!/usr/bin/python3
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


class logCount(logging.Handler):
    """Custom log handler keeping track of issued log messages"""

    class LogType:
        """Log message type"""

        def __init__(self) -> None:
            self.warnings = 0
            self.errors = 0

    def __init__(self) -> None:
        super().__init__()
        self.count = self.LogType()

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelname == "WARNING":
            self.count.warnings += 1
        if record.levelname in ("ERROR", "FATAL", "CRITICAL"):
            self.count.errors += 1
