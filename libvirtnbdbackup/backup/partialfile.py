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
import glob
import logging
from argparse import Namespace

from libvirtnbdbackup import exceptions


log = logging.getLogger()


def _exists(args: Namespace) -> int:
    """Check for possible partial backup files"""
    partialFiles = glob.glob(f"{args.output}/*.partial")
    return len(partialFiles) > 0


def exists(args: Namespace) -> bool:
    """Check if target directory has an partial backup,
    makes backup utility exit errnous in case backup
    type is full or inc"""
    if args.level in ("inc", "diff") and args.stdout is False and _exists(args) is True:
        log.error("Partial backup found in target directory: [%s]", args.output)
        log.error("One of the last backups seems to have failed.")
        log.error("Consider re-executing full backup.")
        return True

    return False


def rename(targetFilePartial: str, targetFile: str) -> None:
    """After backup, move .partial file to real
    target file"""
    try:
        os.rename(targetFilePartial, targetFile)
    except OSError as e:
        raise exceptions.DiskBackupFailed(f"Failed to rename file: [{e}]") from e
