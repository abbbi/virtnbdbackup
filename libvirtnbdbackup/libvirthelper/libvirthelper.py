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
import glob
import os
from xml.etree import ElementTree
from collections import namedtuple
import logging
import libvirt


def libvirt_ignore(_ignore, _err):
    """this is required so libvirt.py does not report errors to stderr
    which it does by default. Error messages are fetched accordingly
    using exceptions.
    """


libvirt.registerErrorHandler(f=libvirt_ignore, ctx=None)

log = logging.getLogger(__name__)


class client:
    """Libvirt related functions"""

    def __init__(self):
        self._conn = self._connect()
        self._domObj = None

    @staticmethod
    def _connect():
        """return libvirt conneciton handle"""
        URI = "qemu:///system"
        try:
            return libvirt.open(URI)
        except libvirt.libvirtError as e:
            log.error("Cant connect libvirt daemon: %s", e)
            sys.exit(1)

    def getDomain(self, name):
        """Lookup domain"""
        return self._conn.lookupByName(name)

    @staticmethod
    def domainOffline(domObj):
        """Returns true if domain is not in running state"""
        state, _ = domObj.state()
        log.debug("Domain state returned by libvirt: [%s]", state)
        return state != libvirt.VIR_DOMAIN_RUNNING

    @staticmethod
    def hasIncrementalEnabled(domObj):
        """Check if virtual machine has enabled required capabilities
        for incremental backup
        """
        tree = ElementTree.fromstring(domObj.XMLDesc(0))
        for target in tree.findall(
            "{http://libvirt.org/schemas/domain/qemu/1.0}capabilities"
        ):
            for cap in target.findall(
                "{http://libvirt.org/schemas/domain/qemu/1.0}add"
            ):
                if "incremental-backup" in cap.items()[0]:
                    return True

        return False

    @staticmethod
    def getDomainConfig(domObj):
        """Return Virtual Machine configuration as XML"""
        return domObj.XMLDesc(0)

    @staticmethod
    def getDomainDisks(vmConfig, excludedDisks, includeDisk, includeRaw):
        """Parse virtual machine configuration for disk devices, filter
        all non supported devices
        """
        DomainDisk = namedtuple(
            "DomainDisk",
            ["diskTarget", "diskFormat", "diskFileName", "diskPath", "backingStores"],
        )
        tree = ElementTree.fromstring(vmConfig)
        devices = []

        excludeList = None
        if excludedDisks is not None:
            excludeList = excludedDisks.split(",")

        driver = None
        device = None
        diskFileName = None
        diskPath = None
        for target in tree.findall("devices/disk"):
            for src in target.findall("target"):
                dev = src.get("dev")

            if excludeList is not None:
                if dev in excludeList:
                    log.warning("Excluding Disks %s from backup as requested", dev)
                    continue

            # ignore attached lun or direct access block devices
            if target.get("type") == "block":
                log.warning(
                    "Ignoring device %s does not support changed block tracking.", dev
                )
                continue

            device = target.get("device")
            if device is not None:
                if device == "lun":
                    log.warning(
                        "Ignoring lun disk %s does not support changed block tracking.",
                        dev,
                    )
                    continue

            # ignore disk which use raw format, they do not support CBT
            driver = target.find("driver")
            if driver is not None:
                diskFormat = driver.get("type")
                if diskFormat == "raw" and includeRaw is False:
                    log.warning(
                        "Raw disk %s excluded by default, use option --raw to include.",
                        dev,
                    )
                    continue

            # attempt to get original disk file name
            source = target.find("source")
            if source is not None:
                diskSrc = source.get("file")
                if diskSrc:
                    diskFileName = os.path.basename(diskSrc)
                    diskPath = diskSrc

            if target.get("device") == "cdrom":
                continue

            if includeDisk is not None and dev != includeDisk:
                log.info(
                    "Skipping disk: %s as requested: does not match disk %s",
                    dev,
                    includeDisk,
                )
                continue

            backingStoreFiles = []
            backingStore = target.find("backingStore")
            while backingStore is not None:
                backingStoreSource = backingStore.find("source")

                if backingStoreSource is not None:
                    backingStoreFiles.append(backingStoreSource.get("file"))

                if backingStore.find("backingStore"):
                    backingStore = backingStore.find("backingStore")
                else:
                    backingStore = None

            devices.append(
                DomainDisk(dev, diskFormat, diskFileName, diskPath, backingStoreFiles)
            )

        return devices

    def _indentXml(self, top):
        """Indent xml output for debug logging"""
        try:
            ElementTree.indent(top)
        except Exception as errmsg:
            log.debug("Unable to indent xml: [%s]", errmsg)

        xml = ElementTree.tostring(top).decode()
        log.debug("\n%s", xml)

        return xml

    def _createBackupXml(
        self, diskList, parentCheckpoint, scratchFilePath, socketFilePath
    ):
        """Create XML file for starting an backup task using libvirt API."""
        top = ElementTree.Element("domainbackup", {"mode": "pull"})
        ElementTree.SubElement(
            top, "server", {"transport": "unix", "socket": f"{socketFilePath}"}
        )
        disks = ElementTree.SubElement(top, "disks")

        if parentCheckpoint is not False:
            inc = ElementTree.SubElement(top, "incremental")
            inc.text = parentCheckpoint

        for disk in diskList:
            scratchId = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=5)
            )
            scratchFile = "%s/backup.%s.%s" % (
                scratchFilePath,
                scratchId,
                disk.diskTarget,
            )
            log.debug("Using scratch file: %s", scratchFile)
            dE = ElementTree.SubElement(disks, "disk", {"name": disk.diskTarget})
            ElementTree.SubElement(dE, "scratch", {"file": f"{scratchFile}"})

        xml = self._indentXml(top)

        return xml

    def _createCheckpointXml(self, diskList, parentCheckpoint, checkpointName):
        """Create valid checkpoint XML file which is passed to libvirt API"""
        top = ElementTree.Element("domaincheckpoint")
        desc = ElementTree.SubElement(top, "description")
        desc.text = "Backup checkpoint"
        name = ElementTree.SubElement(top, "name")
        name.text = checkpointName
        if parentCheckpoint is not False:
            pct = ElementTree.SubElement(top, "parent")
            cptName = ElementTree.SubElement(pct, "name")
            cptName.text = parentCheckpoint
        disks = ElementTree.SubElement(top, "disks")
        for disk in diskList:
            # No persistent checkpoint will be created for raw disks,
            # because it is not supported. Backup will only be crash
            # consistent. If we would like to create a consistent
            # backup, we would have to create an snapshot for these
            # kind of disks.
            if disk.diskFormat != "raw":
                ElementTree.SubElement(disks, "disk", {"name": disk.diskTarget})

        xml = self._indentXml(top)

        return xml

    def fsFreeze(self, domObj):
        """Attempt to freeze domain filesystems using qemu guest agent"""
        try:
            domObj.fsFreeze()
            log.info("Freeze filesystems.")
            return True
        except libvirt.libvirtError as errmsg:
            log.warning(errmsg)
            return False

    def fsThaw(self, domObj):
        """Thaw freeze filesystems"""
        try:
            domObj.fsThaw()
            log.info("Thawed filesystems.")
            return True
        except libvirt.libvirtError as errmsg:
            log.warning(errmsg)
            return False

    def startBackup(
        self,
        domObj,
        diskList,
        backupLevel,
        checkpointName,
        parentCheckpoint,
        scratchFilePath,
        socketFilePath,
    ):
        """Attempt to start pull based backup task using  XMl description"""
        backupXml = self._createBackupXml(
            diskList, parentCheckpoint, scratchFilePath, socketFilePath
        )
        checkpointXml = None
        freezed = False
        try:
            if backupLevel != "copy":
                checkpointXml = self._createCheckpointXml(
                    diskList, parentCheckpoint, checkpointName
                )
            freezed = self.fsFreeze(domObj)
            domObj.backupBegin(backupXml, checkpointXml)
            if freezed is True:
                self.fsThaw(domObj)
        except Exception as errmsg:
            # check if filesystem is freezted and thaw
            # in case creating checkpoint fails.
            if freezed is True:
                self.fsThaw(domObj)
            raise errmsg

    def checkpointExists(self, domObj, checkpointName):
        """Check if an checkpoint exists"""
        return domObj.checkpointLookupByName(checkpointName)

    def removeAllCheckpoints(self, domObj, checkpointList, args, defaultCheckpointName):
        """Remove all existing checkpoints for a virtual machine,
        used during FULL backup to reset checkpoint chain
        """

        # clean persistent storage in args.checkpointdir
        log.debug("Cleaning up persistent storage %s", args.checkpointdir)
        try:
            for checkpointFile in glob.glob(f"{args.checkpointdir}/*.xml"):
                log.debug("Remove checkpoint file: %s", checkpointFile)
                os.remove(checkpointFile)
        except OSError as e:
            log.error(
                "Unable to clean persistent storage %s: %s", args.checkpointdir, e
            )
            return False

        if checkpointList is None:
            cpts = domObj.listAllCheckpoints()
            if cpts:
                for cpt in domObj.listAllCheckpoints():
                    if self.deleteCheckpoint(cpt, defaultCheckpointName) is False:
                        return False
            return True

        for checkpoint in checkpointList:
            cptObj = self.checkpointExists(domObj, checkpoint)
            if cptObj:
                if self.deleteCheckpoint(cptObj, defaultCheckpointName) is False:
                    return False
        return True

    def deleteCheckpoint(self, cptObj, defaultCheckpointName):
        """Delete checkpoint"""
        checkpointName = cptObj.getName()
        if defaultCheckpointName not in checkpointName:
            log.debug(
                "Skipping checkpoint removal: [%s]: not from this application",
                checkpointName,
            )
            return True
        log.debug("Attempt to remove checkpoint: [%s]", checkpointName)
        try:
            cptObj.delete()
            log.debug("Removed checkpoint: [%s]", checkpointName)
            return True
        except libvirt.libvirtError as errmsg:
            log.error("Error during checkpoint removal: [%s]", errmsg)
            return False

    def stopBackup(self, domObj):
        """Cancel the backup task using job abort"""
        try:
            return domObj.abortJob(), None
        except libvirt.libvirtError as err:
            log.warning("Unable to stop backup job: [%s]", err)
            return False

    def redefineCheckpoints(self, domObj, args):
        """Redefine checkpoints from persistent storage"""
        # get list of all .xml files in checkpointdir
        log.info("Loading checkpoint list from: [%s]", args.checkpointdir)
        try:
            checkpointList = glob.glob(f"{args.checkpointdir}/*.xml")
            checkpointList.sort(key=os.path.getmtime)
        except Exception as e:
            log.error(
                "Unable to get checkpoint list from [%s]: %s", args.checkpointdir, e
            )
            return False

        for checkpointFile in checkpointList:
            log.debug("Loading checkpoint config from: [%s]", checkpointFile)
            try:
                with open(checkpointFile, "rb") as f:
                    checkpointConfig = f.read()
                    root = ElementTree.fromstring(checkpointConfig)
            except ElementTree.ParseError as e:
                log.error(
                    "Unable to load checkpoint config from [%s]: %s", checkpointFile, e
                )
                return False

            try:
                checkpointName = root.find("name").text
            except ElementTree.ParseError as e:
                log.error("Unable to find checkpoint name: [%s]", e)
                return False

            try:
                _ = domObj.checkpointLookupByName(checkpointName)
                log.debug("Checkpoint [%s] found", checkpointName)
                continue
            except libvirt.libvirtError as e:
                # ignore VIR_ERR_NO_DOMAIN_CHECKPOINT, report other errors
                if e.get_error_code() != libvirt.VIR_ERR_NO_DOMAIN_CHECKPOINT:
                    log.error("libvirt error: %s", e)
                    return False

            log.info("Redefine missing checkpoint: [%s]", checkpointName)
            try:
                domObj.checkpointCreateXML(
                    checkpointConfig, libvirt.VIR_DOMAIN_CHECKPOINT_CREATE_REDEFINE
                )
            except libvirt.libvirtError as e:
                log.error("Unable to redefine checkpoint: [%s]: %s", checkpointName, e)
                return False

        return True

    def backupCheckpoint(self, domObj, args, checkpointName):
        """save checkpoint config to persistent storage"""
        checkpointFile = f"{args.checkpointdir}/{checkpointName}.xml"
        log.info("Saving checkpoint config to: %s", checkpointFile)
        try:
            with open(checkpointFile, "w") as f:
                c = domObj.checkpointLookupByName(checkpointName)
                f.write(c.getXMLDesc())
                return True
        except OSError as errmsg:
            log.error(
                "Unable to save checkpoint config to file: [%s]: %s",
                checkpointFile,
                errmsg,
            )
            return False

    def hasforeignCheckpoint(self, domObj, defaultCheckpointName):
        """Check if the virtual machine has an checkpoint which was not
        created by virtnbdbackup

        If an user or a third party utility creates an checkpoint,
        it is in line with the complete checkpoint chain, but
        virtnbdbackup does not save it. We can ensure consistency
        only if the complete chain of checkpoints is created by
        ourself. In case we detect an checkpoint that does not
        match our name, return so.
        """
        cpts = domObj.listAllCheckpoints()
        if cpts:
            for cpt in cpts:
                checkpointName = cpt.getName()
                if defaultCheckpointName not in checkpointName:
                    return checkpointName
        return None
