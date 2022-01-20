import os
import json
import subprocess


class qemuHelper:
    """Wrapper for qemu executables"""

    def __init__(self, exportName):
        self.exportName = exportName

    def map(self, backupSocket):
        extentMap = subprocess.run(
            f"qemu-img map --output json 'nbd+unix:///{self.exportName}?socket={backupSocket}'",
            shell=True,
            check=1,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        return json.loads(extentMap.stdout)

    def create(self, targetFile, fileSize, diskFormat):
        subprocess.run(
            f"qemu-img create -f {diskFormat} '{targetFile}' {fileSize}",
            shell=True,
            check=1,
            stdout=subprocess.PIPE,
        )

    def startRestoreNbdServer(self, targetFile, socketFile):
        """Start NBD endpoint for restoring data

        Process will end itself after last connection has
        finished.
        """
        p = subprocess.Popen(
            [
                "qemu-nbd",
                "--discard=unmap",
                "--format=qcow2",
                "-x",
                f"{self.exportName}",
                f"{targetFile}",
                "-k",
                f"{socketFile}",
            ],
            close_fds=True,
        )

        return p.pid

    def startBackupNbdServer(self, diskFormat, diskFile, socketFile):
        """Start NBD Service for Disk device in order to query extend information and
        allow for backup of offline domain

        Process will not end itself and must be stopped manually
        """
        p = subprocess.Popen(
            [
                "qemu-nbd",
                f"--format={diskFormat}",
                "-x",
                f"{self.exportName}",
                f"{diskFile}",
                "-k",
                f"{socketFile}",
                "-t",
                "-e 2",
                "--detect-zeroes=on",
            ],
            close_fds=True,
        )

        return p.pid
