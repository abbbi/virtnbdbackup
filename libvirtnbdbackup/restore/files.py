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
import logging
from argparse import Namespace
from libvirtnbdbackup import virt
from libvirtnbdbackup.restore import vmconfig
from libvirtnbdbackup import common as lib


def restore(args: Namespace, vmConfig: str, virtClient: virt.client) -> None:
    """Notice user if backed up vm had loader / nvram"""
    config = vmconfig.read(vmConfig)
    info = virtClient.getDomainInfo(config)

    for setting, val in info.items():
        f = lib.getLatest(args.input, f"*{os.path.basename(val)}*", -1)
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
