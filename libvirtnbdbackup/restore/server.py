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
from libvirtnbdbackup.qemu import util as qemu
from libvirtnbdbackup.ssh.exceptions import sshError
from libvirtnbdbackup.qemu.exceptions import ProcessError
from libvirtnbdbackup.exceptions import RestoreError

log = logging.getLogger("restore")


def setup(args: Namespace, exportName: str, targetFile: str, virtClient: virt.client):
    """Setup NBD process required for restore, either remote or local"""
    qFh = qemu.util(exportName)
    cType: Union[nbdcli.TCP, nbdcli.Unix]
    if not virtClient.remoteHost:
        logging.info("Starting local NBD server on socket: [%s]", args.socketfile)
        proc = qFh.startRestoreNbdServer(targetFile, args.socketfile)
        cType = nbdcli.Unix(exportName, "", args.socketfile)
    else:
        remoteIP = virtClient.remoteHost
        if args.nbd_ip != "":
            remoteIP = args.nbd_ip
        logging.info(
            "Starting remote NBD server on socket: [%s:%s]",
            remoteIP,
            args.nbd_port,
        )
        proc = qFh.startRemoteRestoreNbdServer(args, targetFile)
        cType = nbdcli.TCP(exportName, "", remoteIP, args.tls, args.nbd_port)

    nbdClient = nbdcli.client(cType, False)
    logging.info("Started NBD server, PID: [%s]", proc.pid)
    return nbdClient.connect()


def start(args: Namespace, diskName: str, targetFile: str, virtClient: virt.client):
    """Start NDB Service"""
    try:
        return setup(args, diskName, targetFile, virtClient)
    except ProcessError as errmsg:
        logging.error(errmsg)
        raise RestoreError("Failed to start local NBD server.") from errmsg
    except sshError as errmsg:
        logging.error(errmsg)
        raise RestoreError("Failed to start remote NBD server.") from errmsg
