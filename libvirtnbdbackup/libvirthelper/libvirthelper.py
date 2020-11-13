import libvirt
import logging
import sys
from xml.etree import ElementTree

# this is needed so libvirt.py does not report errors to stderr
# which it does by default. Error messages are fetched accordingly
# using exceptions.
def libvirt_ignore(ignore, err):
    pass
libvirt.registerErrorHandler(f=libvirt_ignore, ctx=None)

class DomainDisk(object):

    """Docstring for DomainDisk. """

    def __init__(self):
        self.diskTarget = None

class client(object):

    """Docstring for libvirtHelper. """
    def __init__(self):
        """TODO: to be defined.

        :host: TODO
        :port: TODO

        """
        self._conn = self._connect()
        self._domObj = None

    def _connect(self):
        URI='qemu:///system'
        try:
            return libvirt.open(URI)
        except libvirt.libvirtError:
            raise

    def _getDomain(self, name):
        return self._conn.lookupByName(name)

    def getDomainDisks(self, domName):
        self.domObj = self._getDomain(domName)
        tree=ElementTree.fromstring(self.domObj.XMLDesc(0))
        devices=[]

        for target in tree.findall("devices/disk"):
            for src in target.findall("target"):
                dev=src.get("dev")

            diskObj = DomainDisk()
            diskObj.diskTarget = dev
            devices.append(diskObj)

        return devices

    def _createBackupXml(self, diskList, parentCheckpoint):
        top = ElementTree.Element('domainbackup', {'mode':'pull'})
        child = ElementTree.SubElement(top, 'server', {'name':'localhost','port':'10809'})
        disks = ElementTree.SubElement(top, 'disks')

        if parentCheckpoint != None:
            inc = ElementTree.SubElement(top, 'incremental')
            inc.text=parentCheckpoint

        for disk in diskList:
            dE = ElementTree.SubElement(disks, 'disk', {'name': disk.diskTarget})
            ElementTree.SubElement(dE, 'scratch', {'file':'/tmp/backup.%s' % disk.diskTarget})

        return ElementTree.tostring(top)

    def _createCheckpointXml(self, diskList, parentCheckpoint, checkpointName):
        top = ElementTree.Element('domaincheckpoint')
        desc = ElementTree.SubElement(top, 'description')
        desc.text='Backup checkpoint'
        name = ElementTree.SubElement(top, 'name')
        name.text=checkpointName
        if parentCheckpoint != None:
            pct = ElementTree.SubElement(top, 'parent')
            cptName = ElementTree.SubElement(pct, 'name')
            cptName.text = parentCheckpoint
        disks = ElementTree.SubElement(top, 'disks')
        for disk in diskList:
            dE = ElementTree.SubElement(disks, 'disk', {'name': disk.diskTarget})

        return ElementTree.tostring(top)

    def startBackup(self, diskList, backupLevel, checkpointName, parentCheckpoint):
        backupXml = self._createBackupXml(diskList, parentCheckpoint)
        checkpointXml = None
        try:
            if backupLevel != "copy":
                checkpointXml = self._createCheckpointXml(
                    diskList,
                    parentCheckpoint,
                    checkpointName
                ).decode()
            self.domObj.backupBegin(backupXml.decode(), checkpointXml)
        except:
            raise

    def checkpointExists(self, checkpointName):
        return self.domObj.checkpointLookupByName(checkpointName)

    def removeAllCheckpoints(self, checkpointList):
        for checkpoint in checkpointList:
            cptObj = self.checkpointExists(checkpoint)
            if cptObj:
                cptObj.delete()

    def stopBackup(self, diskTarget):
        self.domObj.blockJobAbort(diskTarget)
