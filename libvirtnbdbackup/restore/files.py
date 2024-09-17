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
import zlib
import json
import logging
from typing import List
from argparse import Namespace
from libvirtnbdbackup import virt
from libvirtnbdbackup import output
from libvirtnbdbackup.restore import vmconfig
from libvirtnbdbackup.restore import header
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.objects import DomainDisk
from libvirtnbdbackup.sparsestream import streamer
from libvirtnbdbackup.exceptions import RestoreError


def restore(args: Namespace, vmConfig: str, virtClient: virt.client) -> None:
    """Notice user if backed up vm had loader / nvram"""
    config = vmconfig.read(vmConfig)
    info = virtClient.getDomainInfo(config)

    for setting, val in info.items():
        f = lib.getLatest(args.input, f"*{os.path.basename(val)}*", -1)
        if args.restore_root is not None:
            _, _, val_as_relative = os.path.splitroot(val)
            val = os.path.join(args.restore_root, val_as_relative)
        if lib.exists(args, val):
            logging.info(
                "File [%s]: for boot option [%s] already exists, skipping.",
                val,
                setting,
            )
            continue

        logging.info(
            "Restoring configured file [%s] for boot option [%s]", val, setting
        )
        lib.copy(args, f[0], val)


def verify(args: Namespace, dataFiles: List[str]) -> bool:
    """Compute adler32 checksum for exiting data files and
    compare with checksums computed during backup."""
    for dataFile in dataFiles:
        if args.disk is not None and not os.path.basename(dataFile).startswith(
            args.disk
        ):
            continue
        logging.debug("Using buffer size: %s", args.buffsize)
        logging.info("Computing checksum for: %s", dataFile)

        sourceFile = dataFile
        if args.sequence:
            sourceFile = os.path.join(args.input, dataFile)

        with output.openfile(sourceFile, "rb") as vfh:
            adler = 1
            data = vfh.read(args.buffsize)
            while data:
                adler = zlib.adler32(data, adler)
                data = vfh.read(args.buffsize)

        chksumFile = f"{sourceFile}.chksum"
        logging.info("Checksum result: %s", adler)
        if not os.path.exists(chksumFile):
            logging.info("No checksum found, skipping: [%s]", sourceFile)
            continue
        logging.info("Comparing checksum with stored information")
        with output.openfile(chksumFile, "r") as s:
            storedSum = int(s.read())
        if storedSum != adler:
            logging.error("Stored sums do not match: [%s]!=[%s]", storedSum, adler)
            return False

        logging.info("OK")
    return True


def dump(args: Namespace, stream: streamer.SparseStream, dataFiles: List[str]) -> bool:
    """Dump stream contents to json output"""
    logging.info("Dumping saveset meta information")
    entries = []
    for dataFile in dataFiles:
        if args.disk is not None and not os.path.basename(dataFile).startswith(
            args.disk
        ):
            continue
        logging.info(dataFile)

        sourceFile = dataFile
        if args.sequence:
            sourceFile = os.path.join(args.input, dataFile)

        try:
            meta = header.get(sourceFile, stream)
        except RestoreError as e:
            logging.error(e)
            continue

        entries.append(meta)

        if lib.isCompressed(meta):
            logging.info("Compressed stream found: [%s].", meta["compressionMethod"])

    print(json.dumps(entries, indent=4))

    return True


def target(args: Namespace, disk: DomainDisk) -> str:
    """Based on disk information, return target file
    to create during restore."""
    if disk.filename is not None:
        targetFile = os.path.join(args.output, disk.filename)
    else:
        targetFile = os.path.join(args.output, disk.target)

    return targetFile
