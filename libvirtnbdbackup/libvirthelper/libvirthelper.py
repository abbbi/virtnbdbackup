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

    """
        Virtual machine Disk Object

        @diskTarget: target name for virtual disk as defined
        in the configuration. NBD server will use this target
        name as export name
    """

    def __init__(self):
        self.diskTarget = None

class client(object):
    """
        Libvirt related functions
    """

    def __init__(self):
        self._conn = self._connect()
        self._domObj = None

    def _connect(self):
        URI='qemu:///system'
        try:
            return libvirt.open(URI)
        except libvirt.libvirtError:
            raise

    def getDomain(self, name):
        return self._conn.lookupByName(name)

    def hasIncrementalEnabled(self, domObj):
        tree=ElementTree.fromstring(domObj.XMLDesc(0))
        for target in tree.findall("{http://libvirt.org/schemas/domain/qemu/1.0}capabilities"):
            for cap in target.findall("{http://libvirt.org/schemas/domain/qemu/1.0}add"):
                if 'incremental-backup' in cap.items()[0]:
                    return True

        return False

    def getDomainConfig(self, domObj):
        return domObj.XMLDesc(0)

    def getDomainDisks(self, vmConfig):
        tree=ElementTree.fromstring(vmConfig)
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

        if parentCheckpoint != False:
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
        if parentCheckpoint != False:
            pct = ElementTree.SubElement(top, 'parent')
            cptName = ElementTree.SubElement(pct, 'name')
            cptName.text = parentCheckpoint
        disks = ElementTree.SubElement(top, 'disks')
        for disk in diskList:
            dE = ElementTree.SubElement(disks, 'disk', {'name': disk.diskTarget})

        return ElementTree.tostring(top)

    def startBackup(self, domObj, diskList, backupLevel, checkpointName, parentCheckpoint):
        backupXml = self._createBackupXml(diskList, parentCheckpoint)
        checkpointXml = None
        try:
            if backupLevel != "copy":
                checkpointXml = self._createCheckpointXml(
                    diskList,
                    parentCheckpoint,
                    checkpointName
                ).decode()
            domObj.backupBegin(backupXml.decode(), checkpointXml)
        except:
            raise

    def checkpointExists(self, domObj, checkpointName):
        return domObj.checkpointLookupByName(checkpointName)

    def removeAllCheckpoints(self, domObj, checkpointList):
        if checkpointList == None:
            cpts = domObj.listAllCheckpoints()
            if cpts:
                for cpt in domObj.listAllCheckpoints():
                    if 'virtnbdbackup' in cpt.getName():
                        cpt.delete()
            return True

        for checkpoint in checkpointList:
            cptObj = self.checkpointExists(domObj, checkpoint)
            if cptObj:
                cptObj.delete()
        return True

    def stopBackup(self, domObj, diskTarget):
        domObj.blockJobAbort(diskTarget)
