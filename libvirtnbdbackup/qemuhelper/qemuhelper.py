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
        )
        return json.loads(extentMap.stdout)

    def create(self, targetFile, fileSize, diskFormat):
        subprocess.run(
            f"qemu-img create -f {diskFormat} '{targetFile}' {fileSize}",
            shell=True,
            check=1,
            stdout=subprocess.PIPE,
        )

    def startNbdServer(self, targetFile, socketFile):
        p = subprocess.Popen(
            [
                "qemu-nbd",
                "--discard=unmap",
                "--format=qcow2",
                "-x",
                "%s" % self.exportName,
                "%s" % targetFile,
                "-k",
                "%s" % socketFile,
            ],
            close_fds=True,
        )

        return p.pid
