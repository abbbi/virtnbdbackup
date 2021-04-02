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
import sys
import string
import random
import logging
import libvirt
from xml.etree import ElementTree

# this is required so libvirt.py does not report errors to stderr
# which it does by default. Error messages are fetched accordingly
# using exceptions.
def libvirt_ignore(ignore, err):
    pass
libvirt.registerErrorHandler(f=libvirt_ignore, ctx=None)

class DomainDisk(object):
    """ Virtual machine Disk Object

        @diskTarget: target name for virtual disk as defined
        in the configuration. NBD server will use this target
        name as export name
    """
    def __init__(self):
        self.diskTarget = None

class client(object):
    """ Libvirt related functions
    """
    def __init__(self):
        self._conn = self._connect()
        self._domObj = None

    def _connect(self):
        URI='qemu:///system'
        try:
            return libvirt.open(URI)
        except libvirt.libvirtError as e:
            logging.error('Cant connect libvirt daemon: %s', e)
            sys.exit(1)

    def getDomain(self, name):
        """ Lookup domain """
        return self._conn.lookupByName(name)

    def hasIncrementalEnabled(self, domObj):
        """ Check if virtual machine has enabled required capabilities
        for incremental backup
        """
        tree=ElementTree.fromstring(domObj.XMLDesc(0))
        for target in tree.findall("{http://libvirt.org/schemas/domain/qemu/1.0}capabilities"):
            for cap in target.findall("{http://libvirt.org/schemas/domain/qemu/1.0}add"):
                if 'incremental-backup' in cap.items()[0]:
                    return True

        return False

    def getDomainConfig(self, domObj):
        """ Return Virtual Machine configuration as XML
        """
        return domObj.XMLDesc(0)

    def getDomainDisks(self, vmConfig, excludedDisks):
        """ Parse virtual machine configuration for disk devices, filter
        all non supported devices
        """
        tree=ElementTree.fromstring(vmConfig)
        devices=[]

        excludeList = None
        if excludedDisks != None:
            excludeList = excludedDisks.split(',')

        driver = None
        device = None
        for target in tree.findall("devices/disk"):
            for src in target.findall("target"):
                dev=src.get("dev")

            if excludeList != None:
                if dev in excludeList:
                    logging.warning(
                        'Excluding Disks %s from backup as requested',
                        dev
                    )
                    continue

            # ignore attached lun or direct access block devices
            if target.get('type') == "block":
                logging.warning(
                    'Ignoring device %s does not support changed block tracking.',
                    dev
                )
                continue

            device = target.get('device')
            if device != None:
                if device == "lun":
                    logging.warning(
                        'Ignoring lun disk %s does not support changed block tracking.',
                        dev
                    )
                    continue

            # ignore disk which use raw format, they do not support CBT
            driver = target.find('driver')
            if driver != None:
                if driver.get('type') == "raw":
                    logging.warning(
                        'Ignoring raw disk %s does not support changed block tracking.',
                        dev
                    )
                    continue
            if target.get('device') == "cdrom":
                continue

            diskObj = DomainDisk()
            diskObj.diskTarget = dev
            devices.append(diskObj)

        return devices

    def _createBackupXml(self, diskList, parentCheckpoint, scratchFilePath,
                         socketFilePath):
        """ Create XML file for starting an backup task using libvirt API.
        """
        top = ElementTree.Element('domainbackup', {'mode':'pull'})
        ElementTree.SubElement(
            top,
            'server', { 'transport':'unix', 'socket':'%s' % socketFilePath }
        )
        disks = ElementTree.SubElement(top, 'disks')

        if parentCheckpoint != False:
            inc = ElementTree.SubElement(top, 'incremental')
            inc.text=parentCheckpoint

        for disk in diskList:
            scratchId = ''.join(random.choices(
                string.ascii_uppercase + string.digits,
                k=5
            ))
            scratchFile = '%s/backup.%s.%s' % (
                scratchFilePath,
                scratchId,
                disk.diskTarget
            )
            logging.debug('Using scratchfile: %s', scratchFile)
            dE = ElementTree.SubElement(disks, 'disk', {'name': disk.diskTarget})
            ElementTree.SubElement(dE, 'scratch', {'file':'%s' % (scratchFile)})

        return ElementTree.tostring(top).decode()

    def _createCheckpointXml(self, diskList, parentCheckpoint, checkpointName):
        """ Create valid checkpoint XML file which is passed to libvirt API
        """
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
            ElementTree.SubElement(disks, 'disk', {'name': disk.diskTarget})

        return ElementTree.tostring(top).decode()

    def startBackup(self, domObj, diskList, backupLevel, checkpointName,
                    parentCheckpoint, scratchFilePath, socketFilePath):
        """ Attempt to start pull based backup task using  XMl description
        """
        backupXml = self._createBackupXml(
            diskList,
            parentCheckpoint,
            scratchFilePath,
            socketFilePath
        )
        checkpointXml = None
        try:
            if backupLevel != "copy":
                checkpointXml = self._createCheckpointXml(
                    diskList,
                    parentCheckpoint,
                    checkpointName
                )

            freezed = False
            try:
                domObj.fsFreeze()
                freezed = True
                logging.info('Freezed filesystems.')
            except Exception as e:
                logging.warning(e)

            domObj.backupBegin(backupXml, checkpointXml)

            if freezed is True:
                try:
                    domObj.fsThaw()
                    logging.info('Thawed filesystems.')
                except Exception as e:
                    logging.warning(e)
        except:
            raise

    def checkpointExists(self, domObj, checkpointName):
        """ Check if an checkpoint exists
        """
        return domObj.checkpointLookupByName(checkpointName)

    def removeAllCheckpoints(self, domObj, checkpointList):
        """ Remove all existing checkpoints for a virtual machine,
        used during FULL backup to reset checkpoint chain
        """
        if checkpointList is None:
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
        """ Cancel the backup task using block job abort
        """
        return domObj.blockJobAbort(diskTarget)
