"""
    Copyright (C) 2021  Michael Ablassmeier <abi@grinser.de>

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
import subprocess
from libvirtnbdbackup.qemuhelper import exceptions

log = logging.getLogger(__name__)


class qemuHelper:
    """Wrapper for qemu executables"""

    def __init__(self, exportName):
        self.exportName = exportName

    def map(self, backupSocket, metaContext):
        """Read extent map using nbdinfo utility"""
        metaOpt = ""
        if metaContext is not None:
            metaOpt = f"--map={metaContext}"

        cmd = (
            f"nbdinfo --json {metaOpt} "
            f"'nbd+unix:///{self.exportName}?socket={backupSocket}'"
        )
        log.debug("Starting CMD: [%s]", cmd)
        extentMap = subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        return json.loads(extentMap.stdout)

    @staticmethod
    def create(targetFile, fileSize, diskFormat):
        """Create the target qcow image"""
        subprocess.run(
            f"qemu-img create -f {diskFormat} '{targetFile}' {fileSize}",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
        )

    def startRestoreNbdServer(self, targetFile, socketFile):
        """Start nbd server process for restore operation"""
        cmd = [
            "qemu-nbd",
            "--discard=unmap",
            "--format=qcow2",
            "-x",
            f"{self.exportName}",
            f"{targetFile}",
            "-k",
            f"{socketFile}",
            "--fork",
        ]
        return self._runcmd(cmd, socketFile)

    def startBackupNbdServer(self, diskFormat, diskFile, socketFile, bitMap):
        """Start nbd server process for offline backup operation"""
        bitmapOpt = "--"
        if bitMap is not None:
            bitmapOpt = f"--bitmap={bitMap}"

        cmd = [
            "qemu-nbd",
            "-r",
            f"--format={diskFormat}",
            "-x",
            f"{self.exportName}",
            f"{diskFile}",
            "-k",
            f"{socketFile}",
            "-t",
            "-e 2",
            "--fork",
            "--detect-zeroes=on",
            f"--pid-file={socketFile}.pid",
            bitmapOpt,
        ]
        return self._runcmd(cmd, socketFile)

    @staticmethod
    def _runcmd(cmdLine, socketFile):
        """Start NBD Service"""
        logFile = f"{socketFile}.nbdserver.log"

        log.debug("CMD: %s", " ".join(cmdLine))

        try:
            logHandle = open(logFile, "w+")
            log.debug("Temporary logfile: %s", logFile)
        except OSError as errmsg:
            return errmsg

        p = subprocess.Popen(
            cmdLine,
            close_fds=True,
            stderr=logHandle,
            stdout=logHandle,
        )

        p.wait()
        log.debug("Return code: %s", p.returncode)
        err = None
        if p.returncode != 0:
            p.wait()
            log.debug("Read error messages from logfile")
            logHandle.flush()
            logHandle.close()
            try:
                err = open(logFile, "r").read().strip()
            except OSError as errmsg:
                raise exceptions.NbdServerProcessError(
                    f"Cant start NBD Server: Unable to get error message: {errmsg}"
                )

            raise exceptions.NbdServerProcessError(f"Unable to start NBD server: {err}")

        log.debug("Removing temporary logfile: %s", logFile)
        os.remove(logFile)

        log.debug("Started process, returning: %s", err)
        return err
