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
import os, zlib
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


log = logging.getLogger()

def adler32_full_file(path: str, bufsize: int = 8 * 1024 * 1024) -> int:
    """
    Compute Adler-32 over the entire file, matching virtnbdrestore's verify path.
    """
    csum = 1  # zlib.adler32 seed
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""):
            csum = zlib.adler32(chunk, csum)
    return csum & 0xFFFFFFFF

def _fsync_file(path: str) -> None:
    try:
        with open(path, "rb", buffering=0) as f:
            os.fsync(f.fileno())
    except Exception:
        pass

def write_checksum_sidecar(target_file: str, crc: int) -> None:
    sidecar = f"{target_file}.chksum"
    with open(sidecar, "w") as fh:
        fh.write(f"{crc}\n")
    try:
        with open(sidecar, "rb", buffering=0) as f:
            os.fsync(f.fileno())
    except Exception:
        pass
        

def backupChecksum(fileStream, targetFile):
    """Save the calculated adler32 checksum, it can be verified
    by virtnbdbrestore's verify function.'"""
    checksum = fileStream.checksum()
    logging.info("Checksum for file: [%s]:[%s]", targetFile, checksum)
    chksumfile = f"{targetFile}.chksum"
    logging.info("Saving checksum to: [%s]", chksumfile)
    with output.openfile(chksumfile, "w") as cf:
        cf.write(f"{checksum}")


def backupConfig(args: Namespace, vmConfig: str) -> Union[str, None]:
    """Save domain XML config file"""
    configFile = f"{args.output}/vmconfig.{lib.getIdent(args)}.xml"
    log.info("Saving VM config to: [%s]", configFile)
    try:
        with output.openfile(configFile, "wb") as fh:
            fh.write(vmConfig.encode())
        return configFile
    except OutputException as e:
        log.error("Failed to save VM config: [%s]", e)
        return None


def backupDiskInfo(args: Namespace, disk: DomainDisk):
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
        with output.openfile(configFile, "wb") as fh:
            fh.write(info.out.encode())
        log.info("Saved qcow image config to: [%s]", configFile)
        if args.stdout is True:
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


def backupAutoStart(args: Namespace) -> None:
    """Save information if virtual machine was marked
    for autostart during system boot"""
    log.info("Autostart setting configured for virtual machine.")
    autoStartFile = f"{args.output}/autostart.{lib.getIdent(args)}"
    try:
        with output.openfile(autoStartFile, "wb") as fh:
            fh.write(b"True")
    except OutputException as e:
        log.warning("Failed to save autostart information: [%s]", e)


def saveFiles(
    args: Namespace,
    vmConfig: str,
    disks: List[DomainDisk],
    fileStream: Union[output.target.Directory, output.target.Zip],
    logFile: str,
):
    """Save additional files such as virtual machine configuration
    and UEFI / kernel images"""
    configFile = backupConfig(args, vmConfig)

    backupBootConfig(args)
    for disk in disks:
        if disk.format.startswith("qcow"):
            backupDiskInfo(args, disk)
    if args.stdout is True:
        addFiles(args, configFile, fileStream, logFile)


def addFiles(args: Namespace, configFile: Union[str, None], zipStream, logFile: str):
    """Add backup log and other files to zip archive"""
    if configFile is not None:
        log.info("Adding vm config to zipfile")
        zipStream.zipStream.write(configFile, configFile)
    if args.level in ("full", "inc"):
        log.info("Adding checkpoint info to zipfile")
        zipStream.zipStream.write(args.cpt.file, args.cpt.file)
        for dirname, _, files in os.walk(args.checkpointdir):
            zipStream.zipStream.write(dirname)
            for filename in files:
                zipStream.zipStream.write(os.path.join(dirname, filename))

    for setting, val in args.info.items():
        log.info("Adding additional [%s] setting file [%s] to zipfile", setting, val)
        zipStream.zipStream.write(val, os.path.basename(val))

    for diskInfo in args.diskInfo:
        log.info("Adding QCOW image format file [%s] to zipfile", diskInfo)
        zipStream.zipStream.write(diskInfo, os.path.basename(diskInfo))

    log.info("Adding backup log [%s] to zipfile", logFile)
    zipStream.zipStream.write(logFile, logFile)