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
import json
import logging
from argparse import Namespace
from typing import List, Union
import libvirt

from libvirtnbdbackup.virt.client import DomainDisk
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.qemu import util as qemu
from libvirtnbdbackup.qemu.exceptions import ProcessError
from libvirtnbdbackup.ssh.exceptions import sshError
from libvirtnbdbackup.output.exceptions import OutputException
from libvirtnbdbackup.output.target import OutputTarget
from libvirtnbdbackup.common import safeInfo
from libvirtnbdbackup.virt import guest


log = logging.getLogger()


def backupChecksum(fileStream: OutputTarget, targetFile: str) -> None:
    """Save the calculated adler32 checksum, it can be verified
    by virtnbdbrestore's verify function.'"""
    checksum = fileStream.checksum()
    safeInfo("Checksum for file: [%s]:[%s]", targetFile, checksum)
    chksumfile = f"{targetFile}.chksum"
    safeInfo("Saving checksum to: [%s]", chksumfile)
    with fileStream.open(chksumfile, "wb") as checksumStream:
        checksumStream.write(f"{checksum}".encode())


def backupConfig(
    args: Namespace, vmConfig: str, outputTarget: OutputTarget
) -> Union[str, None]:
    """Save domain XML config file"""
    configFile = os.path.join(args.output, f"vmconfig.{lib.getIdent(args)}.xml")
    log.info("Saving VM config to: [%s]", configFile)
    try:
        with outputTarget.open(configFile, "wb") as fh:
            fh.write(vmConfig.encode())
        return configFile
    except OutputException as e:
        log.error("Failed to save VM config: [%s]", e)
        return None


def backupDiskInfo(
    args: Namespace, disk: DomainDisk, outputTarget: OutputTarget
) -> None:
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
        with outputTarget.open(configFile, "wb") as fh:
            fh.write(info.out.encode())
        log.info("Saved qcow image config to: [%s]", configFile)
    except OutputException as e:
        log.warning("Failed to save qcow image config: [%s]", e)


def backupBootConfig(args: Namespace, outputTarget: OutputTarget) -> None:
    """Save domain uefi/nvram/kernel and loader if configured."""
    for setting, val in args.info.items():
        if args.level != "copy":
            tFile = os.path.join(
                args.output, f"{os.path.basename(val)}.{lib.getIdent(args)}"
            )
        else:
            tFile = os.path.join(args.output, f"{os.path.basename(val)}")
        log.info("Save additional boot config [%s] to: [%s]", setting, tFile)
        targetName = os.path.basename(tFile) if args.stdout else tFile
        if args.sshClient:
            with args.sshClient.sftp.open(val, "rb") as source:
                outputTarget.add_stream(source, targetName)
        else:
            outputTarget.add_file(val, targetName)
        args.info[setting] = tFile


def backupAutoStart(args: Namespace, outputTarget: OutputTarget) -> None:
    """Save information if virtual machine was marked
    for autostart during system boot"""
    log.info("Autostart setting configured for virtual machine.")
    autoStartFile = os.path.join(args.output, f"autostart.{lib.getIdent(args)}")
    try:
        with outputTarget.open(autoStartFile, "wb") as fh:
            fh.write(b"True")
    except OutputException as e:
        log.warning("Failed to save autostart information: [%s]", e)


def backupGuestInfo(args: Namespace, outputTarget: OutputTarget) -> None:
    """Save OS related information"""
    osInfoFile = os.path.join(args.output, f"osinfo.{lib.getIdent(args)}")
    try:
        with outputTarget.open(osInfoFile, "wb") as fh:
            fh.write(json.dumps(args.guestInfo, indent=4).encode())
        log.info("Saved guest related osinfo to [%s]", osInfoFile)
    except OutputException as e:
        log.warning("Failed to save osinfo data: [%s]", e)


def backupBitlockerRecoveryKey(
    args: Namespace, domObj: libvirt.virDomain, outputTarget: OutputTarget
) -> None:
    """Save bitlocker recovery keys"""
    try:
        bde = guest.Exec(domObj, "manage-bde.exe", ["-status"])
        log.info("Bitlocker tools detected, attempting to backup recovery keys.")
        log.debug(bde)
    except libvirt.libvirtError:
        log.info("System does not appear to have bitlocker tools installed, skipping.")

    for i in range(0, args.guestInfo["fs.count"]):
        vol = args.guestInfo.get(f"fs.{i}.mountpoint", None)
        if not vol:
            continue
        if not ":" in vol:
            log.info("Skipping volume: [%s]", vol)
            continue

        vol = vol.replace("\\", "")
        log.info("Check if bitlocker is enabled for volume: [%s]", vol)
        try:
            status = guest.Exec(
                domObj, "manage-bde.exe", ["-status", "-ProtectionAsErrorLevel", vol]
            )
        except RuntimeError as e:
            log.info(
                "Bitlocker seems disabled for volume [%s], skipping: see debug log for details.",
                vol,
            )
            continue
        try:
            protectors = guest.Exec(
                domObj, "manage-bde.exe", ["-protectors", "-get", vol]
            )
        except RuntimeError:
            log.warning(
                "Unable to extract recovery key for volume [%s], see debug log for error details.",
                vol,
            )
            continue
        except (TimeoutError, libvirt.libvirtError) as e:
            log.warning("Unable to pull recovery keys for [%s]: %s", vol, e)
            continue

        keyFile = os.path.join(
            args.output,
            f"bitlocker.recovery.key.{vol.replace(':','')}.{lib.getIdent(args)}",
        )
        try:
            with outputTarget.open(keyFile, "wb") as fh:
                fh.write(protectors.encode())
            log.info("Saved Bitlocker recovery key to [%s]", keyFile)
        except OutputException as e:
            log.warning("Failed to save recovery key: [%s]", e)


def saveFiles(
    args: Namespace,
    vmConfig: str,
    disks: List[DomainDisk],
    fileStream: OutputTarget,
    logFile: str,
):
    """Save additional files such as virtual machine configuration
    and UEFI / kernel images"""
    backupConfig(args, vmConfig, fileStream)

    backupBootConfig(args, fileStream)
    for disk in disks:
        if disk.format.startswith("qcow"):
            backupDiskInfo(args, disk, fileStream)
    if args.stdout is True:
        addFiles(args, fileStream, logFile)


def addFiles(
    args: Namespace,
    outputTarget: OutputTarget,
    logFile: str,
) -> None:
    """Add backup metadata through the output target plugin."""
    if args.level in ("full", "inc"):
        log.info("Adding checkpoint info to zipfile")
        outputTarget.add_file(args.cpt.file, args.cpt.file)
        outputTarget.add_tree(args.checkpointdir)

    log.info("Adding backup log [%s] to zipfile", logFile)
    outputTarget.add_file(logFile, logFile)
