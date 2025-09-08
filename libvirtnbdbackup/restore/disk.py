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
import logging
from argparse import Namespace
from libvirtnbdbackup import virt
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.objects import DomainDisk
from libvirtnbdbackup.restore import server
from libvirtnbdbackup.restore import files
from libvirtnbdbackup.restore import image
from libvirtnbdbackup.restore import header
from libvirtnbdbackup.restore import data
from libvirtnbdbackup.restore import vmconfig
from libvirtnbdbackup.sparsestream import types
from libvirtnbdbackup.sparsestream import streamer
from libvirtnbdbackup.exceptions import RestoreError, UntilCheckpointReached
from libvirtnbdbackup.nbdcli.exceptions import NbdConnectionTimeout


def _backingstore(args: Namespace, disk: DomainDisk) -> None:
    """If an virtual machine was running on an snapshot image,
    warn user, the virtual machine configuration has to be
    adjusted before starting the VM is possible.

    User created external or internal Snapshots are not part of
    the backup.
    """
    if len(disk.backingstores) > 0 and not args.adjust_config:
        logging.warning(
            "Target image [%s] seems to be a snapshot image.", disk.filename
        )
        logging.warning("Target virtual machine configuration must be altered!")
        logging.warning("Configured backing store images must be changed.")


def restore(  # pylint: disable=too-many-branches,too-many-statements,too-many-locals
    args: Namespace, ConfigFile: str, virtClient: virt.client
) -> bytes:
    """Handle disk restore operation and adjust virtual machine
    configuration accordingly."""
    stream = streamer.SparseStream(types)
    vmConfig = vmconfig.read(ConfigFile)
    vmConfig = vmconfig.changeVolumePathes(args, vmConfig).decode()
    vmDisks = virtClient.getDomainDisks(args, vmConfig)
    if not vmDisks:
        raise RestoreError("Unable to parse disks from config")

    restConfig: bytes = vmConfig.encode()
    for disk in vmDisks:
        if args.disk not in (None, disk.target):
            logging.info("Skipping disk [%s] for restore", disk.target)
            continue

        restoreDisk = lib.getLatest(args.input, f"{disk.target}*.data")
        logging.debug("Restoring disk: [%s]", restoreDisk)
        if len(restoreDisk) < 1:
            logging.warning(
                "No backup file for disk [%s] found, assuming it has been excluded.",
                disk.target,
            )
            if args.adjust_config is True:
                restConfig = vmconfig.removeDisk(restConfig.decode(), disk.target)
            continue

        targetFile = files.target(args, disk)

        if args.raw and disk.format == "raw":
            logging.info("Restoring raw image to [%s]", targetFile)
            lib.copy(args, restoreDisk[0], targetFile)
            continue

        if "full" not in restoreDisk[0] and "copy" not in restoreDisk[0]:
            logging.error(
                "[%s]: Unable to locate base full or copy backup.", restoreDisk[0]
            )
            raise RestoreError("Failed to locate backup.")

        cptnum = -1
        if args.until is not None:
            cptnum = int(args.until.split(".")[-1])

        meta = header.get(restoreDisk[cptnum], stream)

        try:
            image.create(args, meta, targetFile, args.sshClient)
        except RestoreError as errmsg:
            raise RestoreError("Creating target image failed.") from errmsg

        try:
            connection = server.start(args, meta["diskName"], targetFile, virtClient)
        except NbdConnectionTimeout as e:
            raise RestoreError(e) from e

        for dataFile in restoreDisk:
            try:
                data.restore(args, stream, dataFile, targetFile, connection)
            except UntilCheckpointReached:
                break
            except RestoreError:
                break

        _backingstore(args, disk)
        if args.adjust_config is True:
            restConfig = vmconfig.adjust(args, disk, restConfig.decode(), targetFile)

        logging.debug("Closing NBD connection")
        connection.disconnect()

    if args.adjust_config is True:
        restConfig = vmconfig.removeUuid(restConfig.decode())
        restConfig = vmconfig.setVMName(args, restConfig.decode())

    return restConfig
