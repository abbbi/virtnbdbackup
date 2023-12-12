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
import tempfile
import logging
from argparse import Namespace
from libvirtnbdbackup import output
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.virt.client import DomainDisk


def read(ConfigFile: str) -> str:
    """Read saved virtual machine config'"""
    try:
        return output.openfile(ConfigFile, "rb").read().decode()
    except:
        logging.error("Can't read config file: [%s]", ConfigFile)
        raise


def backingstore(args: Namespace, disk: DomainDisk) -> None:
    """If an virtual machine was running on an snapshot image,
    warn user, the virtual machine configuration has to be
    adjusted before starting the VM is possible"""
    if len(disk.backingstores) > 0 and not args.adjust_config:
        logging.warning(
            "Target image [%s] seems to be a snapshot image.", disk.filename
        )
        logging.warning("Target virtual machine configuration must be altered!")
        logging.warning("Configured backing store images must be changed.")


def restore(args: Namespace, vmConfig: str, adjustedConfig: bytes) -> None:
    """Restore either original or adjusted vm configuration
    to new directory"""
    targetFile = os.path.join(args.output, os.path.basename(vmConfig))
    if args.adjust_config is True:
        if args.sshClient:
            with tempfile.NamedTemporaryFile(delete=True) as fh:
                fh.write(adjustedConfig)
                lib.copy(args, fh.name, targetFile)
        else:
            with output.openfile(targetFile, "wb") as cnf:
                cnf.write(adjustedConfig)
            logging.info("Adjusted config placed in: [%s]", targetFile)
        if args.define is False:
            logging.info("Use 'virsh define %s' to define VM", targetFile)
    else:
        lib.copy(args, vmConfig, targetFile)
        logging.info("Copied original vm config to [%s]", targetFile)
        logging.info("Note: virtual machine config must be adjusted manually.")
