import sh
import os
import json
from time import sleep

class qemuHelper(object):
    """
        Wrapper for qemu executables
    """
    def __init__(self, exportName):
        self.qemuImg = sh.Command("qemu-img")
        self.qemuNbd = sh.Command("qemu-nbd")
        self.exportName = exportName

    def map(self, backupSocket):
        extentMap = self.qemuImg("map", "--output", "json", "nbd+unix:///%s?socket=%s" % (
            self.exportName,
            backupSocket
        )).stdout
        return json.loads(extentMap)

    def create(self, targetDir, fileSize):
        if not os.path.exists(targetDir):
            os.mkdir(targetDir)
        try:
            self.qemuImg("create", "-f", "qcow2", "%s/%s" % (targetDir,self.exportName), "%s" % fileSize)
        except:
            raise

    def startNbdServer(self, targetDir, socketFile):
        try:
            return self.qemuNbd(
                "--discard=unmap", "--format=qcow2","-x", "%s" % (self.exportName),
                "%s/%s" % (targetDir, self.exportName), "-k", "%s" % socketFile,
                _bg=True
            )
        except:
            raise
