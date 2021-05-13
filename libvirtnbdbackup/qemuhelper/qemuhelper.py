import os
import json
import subprocess

class qemuHelper(object):
    """ Wrapper for qemu executables
    """
    def __init__(self, exportName):
        self.exportName = exportName

    def map(self, backupSocket):
        extentMap = subprocess.run("qemu-img map --output json 'nbd+unix:///%s?socket=%s'" % (
            self.exportName,
            backupSocket
        ), shell=True, check=1, stdout=subprocess.PIPE)
        return json.loads(extentMap.stdout)

    def create(self, targetDir, fileSize, diskFormat):
        if not os.path.exists(targetDir):
            os.mkdir(targetDir)
        subprocess.run("qemu-img create -f %s '%s/%s' %s" % (
            diskFormat,
            targetDir,
            self.exportName,
            fileSize
        ), shell=True, check=1, stdout=subprocess.PIPE)

    def startNbdServer(self, targetDir, socketFile):
        p = subprocess.Popen([
            "qemu-nbd",
            "--discard=unmap",
            "--format=qcow2",
            "-x", "%s" % self.exportName,
            "%s/%s" % (targetDir, self.exportName),
            "-k",
            "%s" % socketFile ], close_fds=True)

        return p.pid
