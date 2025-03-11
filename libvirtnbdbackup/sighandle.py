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
import sys
from argparse import Namespace
from typing import Any
from libvirt import virDomain
from libvirtnbdbackup import virt
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.objects import processInfo
from libvirtnbdbackup.qemu import util as qemu


class Backup:
    """Handle signal during backup operation"""

    @staticmethod
    def catch(
        args: Namespace,
        domObj: virDomain,
        virtClient: virt.client,
        log: Any,
        signum: int,
        _,
    ) -> None:
        """Catch signal, attempt to stop running backup job."""
        log.error("Signal caught: %s", signum)

        if args.offline is True:
            log.error("Exiting.")
            sys.exit(1)

        if virtClient.remoteHost != "":
            log.info("Reconnecting remote system to stop backup job.")
            try:
                virtClient = virt.client(args)
                domObj = virtClient.getDomain(args.domain)
            except virt.exceptions.connectionFailed as e:
                log.error("Reconnecting remote host failed: [%s]", e)
                log.error("Unable to stop backup job on remote system.", e)
                sys.exit(1)

        log.info("Cleanup: Stopping backup job.")
        virtClient.stopBackup(domObj)
        virtClient.close()
        sys.exit(1)


class Map:
    """Handle signal during map operation"""

    @staticmethod
    def catch(
        args: Namespace,
        nbdkitProcess: processInfo,
        blockMap,
        log: Any,
        signum,
        _,
    ):
        """Catch signal, attempt to stop processes."""
        log.info("Received signal: [%s]", signum)
        qemu.util("").disconnect(args.device)
        if not args.verbose:
            log.info("Removing temporary blockmap file: [%s]", blockMap.name)
            os.remove(blockMap.name)
            log.info("Removing nbdkit logfile: [%s]", nbdkitProcess.logFile)
            os.remove(nbdkitProcess.logFile)
        lib.killProc(nbdkitProcess.pid)
        sys.exit(0)
