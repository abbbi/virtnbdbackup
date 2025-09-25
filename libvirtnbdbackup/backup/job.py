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
from typing import List
from libvirt import virDomain, libvirtError
from libvirtnbdbackup import virt
from libvirtnbdbackup.virt.client import DomainDisk
from libvirtnbdbackup.virt.exceptions import startBackupFailed


def start(
    args: Namespace,
    virtClient: virt.client,
    domObj: virDomain,
    disks: List[DomainDisk],
) -> bool:
    """Start backup job via libvirt API"""

    paused: bool = False

    if args.pause is True and args.start_domain is False:
        try:
            domObj.suspend()
            paused = True
            logging.info("Paused virtual machine.")
        except libvirtError as e:
            logging.warning("Attempting to pause VM failed: [%s]", e)

    try:
        logging.info("Starting backup job.")
        virtClient.startBackup(
            args,
            domObj,
            disks,
        )
        logging.debug("Backup job started.")
        return True
    except startBackupFailed as e:
        logging.error(e)
    finally:
        if paused is True:
            try:
                domObj.resume()
                logging.info("Resumed virtual machine.")
            except libvirtError as e:
                logging.warning("Attempting to resume VM failed: [%s]", e)

    return False
