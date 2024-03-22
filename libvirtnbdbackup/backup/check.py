"""
    Copyright (C) 2024  Michael Ablassmeier <abi@grinser.de>

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
from libvirt import virDomain
from libvirtnbdbackup import virt
from libvirtnbdbackup import common as lib
from libvirtnbdbackup import exceptions

log = logging.getLogger()


def targetDir(args: Namespace) -> None:
    """Check if target directory backup is started to meets
    all requirements based on the backup level executed"""
    if (
        args.level not in ("copy", "full", "auto")
        and not lib.hasFullBackup(args)
        and not args.stdout
    ):
        raise exceptions.BackupException(
            f"Unable to execute [{args.level}] backup: "
            f"No full backup found in target directory: [{args.output}]"
        )

    if lib.targetIsEmpty(args) and args.level == "auto":
        log.info("Backup mode auto, target folder is empty: executing full backup.")
        args.level = "full"
    elif not lib.targetIsEmpty(args) and args.level == "auto":
        if not lib.hasFullBackup(args):
            raise exceptions.BackupException(
                "Can't execute switch to auto incremental backup: "
                f"specified target folder [{args.output}] does not contain full backup.",
            )
        log.info("Backup mode auto: executing incremental backup.")
        args.level = "inc"
    elif not args.stdout and not args.startonly and not args.killonly:
        if not lib.targetIsEmpty(args):
            raise exceptions.BackupException(
                "Target directory already contains full or copy backup."
            )


def vmstate(args, virtClient: virt.client, domObj: virDomain) -> None:
    """Check virtual machine state before executing backup
    and based on situation, either fallback to regular copy
    backup or attempt to bring VM into paused state"""
    if args.level in ("full", "inc", "diff") and domObj.isActive() == 0:
        args.offline = True
        if args.start_domain is True:
            log.info("Starting domain in paused state")
            if virtClient.startDomain(domObj) == 0:
                args.offline = False
            else:
                log.info("Failed to start VM in paused mode.")

    if args.level == "full" and args.offline is True:
        log.warning("Domain is offline, resetting backup options.")
        args.level = "copy"
        log.warning("New Backup level: [%s].", args.level)
        args.offline = True

    if args.offline is True and args.startonly is True:
        raise exceptions.BackupException(
            "Domain is offline: must be active for this function."
        )


def vmfeature(virtClient: virt.client, domObj: virDomain) -> None:
    """Check if required features are enabled in domain config"""
    if virtClient.hasIncrementalEnabled(domObj) is False:
        raise exceptions.BackupException(
            (
                "Virtual machine does not support required backup features, "
                "please adjust virtual machine configuration."
            )
        )
