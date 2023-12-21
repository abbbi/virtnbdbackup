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
import os
import sys
import shutil
import logging
from argparse import Namespace
from libvirtnbdbackup import common as lib


def executables() -> None:
    """Check if required utils are installed"""
    for exe in ("nbdkit", "qemu-nbd"):
        if not shutil.which(exe):
            logging.error("Please install required [%s] utility.", exe)


def device(args: Namespace) -> None:
    """Check if /dev/nbdX exists, otherwise it is likely
    nbd module isn't loaded on the system"""
    if not args.device.startswith("/dev/nbd"):
        logging.error("Target device [%s] seems not to be an NBD device?", args.device)

    if not lib.exists(args, args.device):
        logging.error(
            "Target device [%s] does not exist, please load nbd module: [modprobe nbd]",
            args.device,
        )


def plugin(args: Namespace) -> str:
    """Attempt to locate the nbdkit plugin that is passed to the
    nbdkit process"""
    pluginFileName = "virtnbd-nbdkit-plugin"
    installDir = os.path.dirname(sys.argv[0])
    nbdkitModule = f"{installDir}/{pluginFileName}"

    if not lib.exists(args, nbdkitModule):
        logging.error("Failed to locate nbdkit plugin: [%s]", pluginFileName)

    return nbdkitModule
