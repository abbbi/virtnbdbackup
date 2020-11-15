import sh
import os
import json
from time import sleep

class qemuHelper(object):

    """Docstring for qemuHelper. """
    def __init__(self, exportName):
        """TODO: to be defined.

        :host: TODO
        :port: TODO

        """
        self.qemuImg = sh.Command("qemu-img")
        self.qemuNbd = sh.Command("qemu-nbd")
        self.exportName = exportName

    def map(self, host="localhost", port="10809"):
        extentMap = self.qemuImg("map", "--output", "json", "nbd://%s:%s/%s" % (
            host,
            port,
            self.exportName
        )).stdout
        return json.loads(extentMap)

    def create(self, targetDir, fileSize):
        if not os.path.exists(targetDir):
            os.mkdir(targetDir)
        try:
            self.qemuImg("create", "-f", "qcow2", "%s/%s" % (targetDir,self.exportName), "%s" % fileSize)
        except:
            raise

    def startNbdServer(self, targetDir):
        try:
            return self.qemuNbd("--verbose","-x", "%s" % (self.exportName), "%s/%s" % (targetDir, self.exportName), _bg=True)
        except:
            raise
