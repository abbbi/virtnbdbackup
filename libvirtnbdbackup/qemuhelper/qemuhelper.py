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

import json
import logging
import tempfile
import subprocess

from libvirtnbdbackup.qemuhelper import exceptions
from libvirtnbdbackup.sshutil import exceptions as sshexceptions
from libvirtnbdbackup.outputhelper import openfile
from libvirtnbdbackup.common.common import processInfo

log = logging.getLogger(__name__)


class qemuHelper:
    """Wrapper for qemu executables"""

    def __init__(self, exportName):
        self.exportName = exportName

    @staticmethod
    def map(cType):
        """Read extent map using nbdinfo utility"""
        metaOpt = "--map"
        if cType.metaContext is not None:
            metaOpt = f"--map={cType.metaContext}"

        cmd = f"nbdinfo --json {metaOpt} " f"'{cType.uri}'"
        log.debug("Starting CMD: [%s]", cmd)
        extentMap = subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        return json.loads(extentMap.stdout)

    def create(self, targetFile, fileSize, diskFormat, sshClient=None):
        """Create the target qcow image"""
        cmd = [
            "qemu-img",
            "create",
            "-f",
            f"{diskFormat}",
            f"{targetFile}",
            f"{fileSize}",
        ]
        if not sshClient:
            return self.runcmd(cmd)

        return sshClient.run(" ".join(cmd))

    def startRestoreNbdServer(self, targetFile, socketFile):
        """Start local nbd server process for restore operation"""
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
        return self.runcmd(cmd)

    @staticmethod
    def _gt(prefix, suffix, delete=False):
        """Create named temporary file."""
        with tempfile.NamedTemporaryFile(
            delete=delete, prefix=prefix, suffix=suffix
        ) as tf1:
            return tf1.name

    @staticmethod
    def _addTls(cmd, certpath):
        """Add required tls related options to qemu-nbd command
        line."""
        cmd.append("--object")
        cmd.append(
            f"tls-creds-x509,id=tls0,endpoint=server,dir={certpath},verify-peer=false"
        )
        cmd.append("--tls-creds tls0")

    def startRemoteRestoreNbdServer(self, args, sshClient, targetFile):
        """Start nbd server process remotely over ssh for restore operation"""
        pidFile = self._gt("qemu-nbd-restore", ".pid")
        logFile = self._gt("qemu-nbd-restore", ".log")
        cmd = [
            "qemu-nbd",
            "--discard=unmap",
            "--format=qcow2",
            "-x",
            f"{self.exportName}",
            f"{targetFile}",
            "-p",
            f"{args.nbd_port}",
            "--pid-file",
            f"{pidFile}",
            "--fork",
        ]
        if args.tls is True:
            self._addTls(cmd, args.tls_cert)
        cmd.append(f"> {logFile} 2>&1")
        try:
            return sshClient.run(" ".join(cmd), pidFile, logFile)
        except sshexceptions.sshutilError:
            logging.error("Executing command failed: check [%s] for errors.", logFile)
            raise

    def startNbdkitProcess(self, args, nbdkitModule, blockMap, fullImage):
        """Execute nbdkit process for virtnbdmap"""
        debug = "0"
        pidFile = self._gt("nbdkit", ".pid")
        if args.verbose:
            debug = "1"
        cmd = [
            "nbdkit",
            "--pidfile",
            f"{pidFile}",
            "-i",
            f"{args.listen_address}",
            "-p",
            f"{args.listen_port}",
            "-e",
            f"{self.exportName}",
            "--filter=blocksize",
            "--filter=cow",
            "-v",
            "python",
            f"{nbdkitModule}",
            f"maxlen={args.blocksize}",
            f"blockmap={blockMap}",
            f"disk={fullImage}",
            f"debug={debug}",
            "-t",
            f"{args.threads}",
        ]
        return self.runcmd(cmd, pidFile=pidFile)

    def startBackupNbdServer(self, diskFormat, diskFile, socketFile, bitMap):
        """Start nbd server process for offline backup operation"""
        bitmapOpt = "--"
        if bitMap is not None:
            bitmapOpt = f"--bitmap={bitMap}"

        pidFile = f"{socketFile}.pid"
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
            f"--pid-file={pidFile}",
            bitmapOpt,
        ]
        return self.runcmd(cmd, pidFile=pidFile)

    def startRemoteBackupNbdServer(
        self, args, diskFormat, targetFile, bitMap, sshClient
    ):
        """Start nbd server process remotely over ssh for restore operation"""
        pidFile = self._gt("qemu-nbd-backup", ".pid")
        logFile = self._gt("qemu-nbd-backup", ".log")
        cmd = [
            "qemu-nbd",
            "-r",
            f"--format={diskFormat}",
            "-x",
            f"{self.exportName}",
            f"{targetFile}",
            "-p",
            f"{args.nbd_port}",
            "--pid-file",
            f"{pidFile}",
            "--fork",
        ]
        if args.nbd_ip is not None:
            cmd.append("-b")
            cmd.append(args.nbd_ip)

        if bitMap is not None:
            cmd.append(f"--bitmap={bitMap}")

        if args.tls is True:
            self._addTls(cmd, args.tls_cert)
        cmd.append(f"> {logFile} 2>&1")
        try:
            return sshClient.run(" ".join(cmd), pidFile, logFile)
        except sshexceptions.sshutilError:
            logging.error("Executing command failed: check [%s] for errors.", logFile)
            raise

    def disconnect(self, device):
        """Disconnect device"""
        logging.info("Disconnecting device [%s]", device)
        cmd = ["qemu-nbd", "-d", f"{device}"]
        return self.runcmd(cmd)

    @staticmethod
    def _readlog(logFile, cmd):
        try:
            with openfile(logFile, "rb") as fh:
                return fh.read().decode().strip()
        except Exception as errmsg:
            raise exceptions.ProcessError(
                f"Error executing [{cmd}] Unable to get error message: {errmsg}"
            )

    @staticmethod
    def _readpipe(p):
        out = p.stdout.read().decode().strip()
        err = p.stderr.read().decode().strip()
        return out, err

    def runcmd(self, cmdLine, pidFile=None, toPipe=False):
        """Execute passed command"""
        logFileName = None
        if toPipe is True:
            logFile = subprocess.PIPE
        else:
            logFile = tempfile.NamedTemporaryFile(
                delete=False, prefix=cmdLine[0], suffix=".log"
            )
            logFileName = logFile.name

        log.debug("CMD: %s", " ".join(cmdLine))
        with subprocess.Popen(
            cmdLine,
            close_fds=True,
            stderr=logFile,
            stdout=logFile,
        ) as p:
            p.wait(5)
            log.debug("Return code: %s", p.returncode)
            err = None
            out = None
            if p.returncode != 0:
                p.wait(5)
                log.info("CMD: %s", " ".join(cmdLine))
                log.debug("Read error messages from logfile")
                if toPipe is True:
                    out, err = self._readpipe(p)
                else:
                    err = self._readlog(logFile.name, cmdLine[0])
                raise exceptions.ProcessError(
                    f"Unable to start [{cmdLine[0]}] error: [{err}]"
                )

            if toPipe is True:
                out, err = self._readpipe(p)

            if pidFile is not None:
                realPid = int(self._readlog(pidFile, ""))
            else:
                realPid = p.pid

            process = processInfo(realPid, logFileName, err, out)
            log.debug("Started [%s] process, returning: %s", cmdLine[0], err)
        return process
