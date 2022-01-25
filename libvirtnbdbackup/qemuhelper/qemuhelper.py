import os
import json
import logging
import subprocess

log = logging.getLogger(__name__)


class qemuHelper:
    """Wrapper for qemu executables"""

    def __init__(self, exportName):
        self.exportName = exportName

    def map(self, backupSocket):
        extentMap = subprocess.run(
            f"qemu-img map --output json 'nbd+unix:///{self.exportName}?socket={backupSocket}'",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        return json.loads(extentMap.stdout)

    def create(self, targetFile, fileSize, diskFormat):
        subprocess.run(
            f"qemu-img create -f {diskFormat} '{targetFile}' {fileSize}",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
        )

    def startRestoreNbdServer(self, targetFile, socketFile):
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

    def _runcmd(self, cmdLine, socketFile):
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
                err = errmsg

        log.debug("Removing temporary logfile: %s", logFile)
        os.remove(logFile)

        log.debug("Started process, returning: %s", err)
        return err
