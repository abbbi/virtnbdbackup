#!/usr/bin/python3
"""
Copyright (C) 2023 Michael Ablassmeier <abi@grinser.de>

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
import logging
from typing import BinaryIO
from argparse import Namespace
from libvirtnbdbackup.virt.client import DomainDisk
from libvirtnbdbackup.common import getIdent, safeInfo


def get(
    args: Namespace, fileStream, targetFile: str, targetFilePartial: str
) -> BinaryIO:
    """Open target file based on output writer"""
    if args.output.startswith("zip"):
        fileStream.open(targetFile)
    else:
        safeInfo("Write data to target file: [%s].", targetFilePartial)
        fileStream.open(targetFilePartial)

    return fileStream


def Set(args: Namespace, disk: DomainDisk, ext: str = "data"):
    """Set Target file name to write data to, used for both data files
    and qemu disk info"""
    targetFile: str = ""
    level = args.level_filename
    if level in ("full", "copy"):
        if disk.format == "raw":
            level = "copy"
        targetFile = os.path.join(args.output, f"{disk.target}.{level}.{ext}")
    elif level in ("inc", "diff"):
        cptName = getIdent(args)
        targetFile = os.path.join(args.output, f"{disk.target}.{level}.{cptName}.{ext}")

    targetFilePartial = f"{targetFile}.partial"

    return targetFile, targetFilePartial
