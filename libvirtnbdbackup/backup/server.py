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
from typing import Union
from libvirtnbdbackup import nbdcli
from libvirtnbdbackup import virt
from libvirtnbdbackup.virt.client import DomainDisk
from libvirtnbdbackup.qemu import util as qemu
from libvirtnbdbackup.objects import processInfo
from libvirtnbdbackup.nbdcli.exceptions import NbdClientException
from libvirtnbdbackup.exceptions import DiskBackupFailed


def setup(args: Namespace, disk: DomainDisk, remoteHost: str, port: int) -> processInfo:
    """Start background qemu-nbd process used during backup
    if domain is offline, in case of remote backup, initiate
    ssh session and start process on remote system."""
    bitMap: str = ""
    if args.level in ("inc", "diff"):
        bitMap = args.cpt.name
    socket = f"{args.socketfile}.{disk.target}"
    if remoteHost != "":
        logging.info(
            "Offline backup, starting remote NBD server, socket: [%s:%s], port: [%s]",
            remoteHost,
            socket,
            port,
        )
        nbdProc = qemu.util(disk.target).startRemoteBackupNbdServer(
            args, disk, bitMap, port
        )
        logging.info("Remote NBD server started, PID: [%s].", nbdProc.pid)
        return nbdProc

    logging.info("Offline backup, starting local NBD server, socket: [%s]", socket)
    nbdProc = qemu.util(disk.target).startBackupNbdServer(
        disk.format, disk.path, socket, bitMap
    )
    logging.info("Local NBD Service started, PID: [%s]", nbdProc.pid)
    return nbdProc


def connect(  # pylint: disable=too-many-arguments
    args: Namespace,
    disk: DomainDisk,
    metaContext: str,
    remoteIP: str,
    port: int,
    virtClient: virt.client,
):
    """Connect to started nbd endpoint"""
    socket = args.socketfile
    if args.offline is True:
        socket = f"{args.socketfile}.{disk.target}"

    cType: Union[nbdcli.TCP, nbdcli.Unix]
    if virtClient.remoteHost != "":
        cType = nbdcli.TCP(disk.target, metaContext, remoteIP, args.tls, port)
    else:
        cType = nbdcli.Unix(disk.target, metaContext, socket)

    nbdClient = nbdcli.client(cType)

    try:
        return nbdClient.connect()
    except NbdClientException as e:
        raise DiskBackupFailed(
            f"NBD endpoint: [{cType}]: connection failed: [{e}]"
        ) from e
