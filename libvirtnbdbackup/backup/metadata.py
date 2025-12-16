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
import logging
from argparse import Namespace
from typing import List, Union

from libvirtnbdbackup import output
from libvirtnbdbackup.virt.client import DomainDisk
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.qemu import util as qemu
from libvirtnbdbackup.qemu.exceptions import ProcessError
from libvirtnbdbackup.ssh.exceptions import sshError
from libvirtnbdbackup.output.exceptions import OutputException
from libvirtnbdbackup.output.base import TargetPlugin
from libvirtnbdbackup.common import safeInfo


log = logging.getLogger()


def backupChecksum(fileStream: TargetPlugin, targetFile: str) -> None:
    """Save the calculated adler32 checksum, it can be verified
    by virtnbdbrestore's verify function.'"""
    checksum = fileStream.checksum()
    if checksum is None:
        return
    safeInfo("Checksum for file: [%s]:[%s]", targetFile, checksum)
    chksumfile = f"{targetFile}.chksum"
    safeInfo("Saving checksum to: [%s]", chksumfile)
    with fileStream.open(chksumfile) as cf:
        cf.write(b"{checksum}")


def backupConfig(
    args: Namespace, fileStream: TargetPlugin, vmConfig: str
) -> Union[str, None]:
    """Save domain XML config file"""
    configFile = f"{args.output}/vmconfig.{lib.getIdent(args)}.xml"
    log.info("Saving VM config to: [%s]", configFile)
    try:
        with fileStream.open(configFile) as fh:
            fh.write(vmConfig.encode())
        return configFile
    except OutputException as e:
        log.error("Failed to save VM config: [%s]", e)
        return None


def backupDiskInfo(args: Namespace, fileStream: TargetPlugin, disk: DomainDisk):
    """Save information about qcow image, used to reconstruct
    the qemu image with the same settings during restore"""
    try:
        info = qemu.util("").info(disk.path, args.sshClient)
    except (
        ProcessError,
        sshError,
    ) as errmsg:
        log.warning("Failed to read qcow image info: [%s]", errmsg)
        return

    configFile = f"{args.output}/{disk.target}.{lib.getIdent(args)}.qcow.json"
    try:
        with fileStream.open(configFile) as fh:
            fh.write(info.out.encode())
        log.info("Saved qcow image config to: [%s]", configFile)
        args.diskInfo.append(configFile)
    except OutputException as e:
        log.warning("Failed to save qcow image config: [%s]", e)


def backupBootConfig(args: Namespace) -> None:
    """Save domain uefi/nvram/kernel and loader if configured."""
    for setting, val in args.info.items():
        if args.level != "copy":
            tFile = f"{args.output}/{os.path.basename(val)}.{lib.getIdent(args)}"
        else:
            tFile = f"{args.output}/{os.path.basename(val)}"
        log.info("Save additional boot config [%s] to: [%s]", setting, tFile)
        lib.copy(args, val, tFile)
        args.info[setting] = tFile


def backupAutoStart(args: Namespace, fileStream: TargetPlugin) -> None:
    """Save information if virtual machine was marked
    for autostart during system boot"""
    log.info("Autostart setting configured for virtual machine.")
    autoStartFile = f"{args.output}/autostart.{lib.getIdent(args)}"
    try:
        with fileStream.open(autoStartFile) as fh:
            fh.write(b"True")
    except OutputException as e:
        log.warning("Failed to save autostart information: [%s]", e)


def saveFiles(
    args: Namespace,
    disks: List[DomainDisk],
    fileStream: TargetPlugin,
):
    """Save additional files such as virtual machine configuration
    and UEFI / kernel images"""
    backupBootConfig(args)
    for disk in disks:
        if disk.format.startswith("qcow"):
            backupDiskInfo(args, fileStream, disk)
