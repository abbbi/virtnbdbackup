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
import os
import string
import random
import glob
import logging
from dataclasses import dataclass
from socket import gethostname
from argparse import Namespace
from typing import Any, Dict, List, Tuple, Optional
from lxml.etree import _Element
from lxml import etree as ElementTree
import libvirt
from libvirtnbdbackup.libvirthelper import exceptions
from libvirtnbdbackup import outputhelper


@dataclass
class DomainDisk:
    """Domain disk object"""

    target: str
    format: str
    filename: str
    path: str
    backingstores: List[str]


def libvirt_ignore(
    _ignore: None, _err: Tuple[int, int, str, int, str, str, None, int, int]
) -> None:
    """this is required so libvirt.py does not report errors to stderr
    which it does by default. Error messages are fetched accordingly
    using exceptions.
    """


libvirt.registerErrorHandler(f=libvirt_ignore, ctx=None)

log = logging.getLogger(__name__)


class client:
    """Libvirt related functions"""

    def __init__(self, uri: Namespace) -> None:
        self.remoteHost = None
        self._conn = self._connect(uri)
        self._domObj = None
        self.libvirtVersion = self._conn.getLibVersion()

    @staticmethod
    def _connectAuth(uri: str, user: str, password: str) -> libvirt.virConnect:
        """Use openAuth if connection string includes authfile or
        username/password are set"""

        def _cred(credentials, user_data) -> None:
            for credential in credentials:
                if credential[0] == libvirt.VIR_CRED_AUTHNAME:
                    credential[4] = user_data[0]
                elif credential[0] == libvirt.VIR_CRED_PASSPHRASE:
                    credential[4] = user_data[1]

        logging.debug("Username: %s", user)
        logging.debug("Password: %s", password)

        try:
            auth: List = [[libvirt.VIR_CRED_AUTHNAME, libvirt.VIR_CRED_PASSPHRASE]]
            if user is not None and password is not None:
                user_data = [user, password]
                auth.append(_cred)
                auth.append(user_data)

            return libvirt.openAuth(uri, auth, 0)
        except libvirt.libvirtError as e:
            raise exceptions.connectionFailed(e) from e

    @staticmethod
    def _connectOpen(uri: str) -> libvirt.virConnect:
        """Open connection with regular libvirt URI for local authentication"""
        try:
            return libvirt.open(uri)
        except libvirt.libvirtError as e:
            raise exceptions.connectionFailed(e) from e

    @staticmethod
    def _reqAuth(uri: str) -> bool:
        """If authentication file is passed or qemu+ssh is used,
        no user and password are required."""
        return "authfile" in uri

    @staticmethod
    def _isSsh(uri: str) -> bool:
        """If authentication file is passed or qemu+ssh is used,
        no user and password are required."""
        return uri.startswith("qemu+ssh")

    def _useAuth(self, args: Namespace) -> bool:
        """Check wether we want to use advanced auth method"""
        if args.uri.startswith("qemu+"):
            return True
        if self._reqAuth(args.uri):
            return True
        if args.user or args.password:
            return True

        return False

    def _connect(self, args: Namespace) -> libvirt.virConnect:
        """return libvirt connection handle"""
        logging.debug("Libvirt URI: [%s]", args.uri)
        if self._useAuth(args):
            logging.debug(
                "Login information specified, connect libvirtd using openAuth function."
            )
            if (
                not self._reqAuth(args.uri)
                and not self._isSsh(args.uri)
                and (not args.user or not args.password)
            ):
                raise exceptions.connectionFailed(
                    "Username (--user) and password (--password) required."
                )
            if not self._isSsh(args.uri):
                conn = self._connectAuth(args.uri, args.user, args.password)
            else:
                conn = self._connectOpen(args.uri)
            if gethostname() != conn.getHostname():
                logging.info(
                    "Connected to remote host: [%s], local host: [%s]",
                    conn.getHostname(),
                    gethostname(),
                )
                self.remoteHost = conn.getHostname()

            return conn

        logging.debug("Connect libvirt using open function.")

        return self._connectOpen(args.uri)

    @staticmethod
    def _getTree(vmConfig: str) -> _Element:
        """Return Etree element for vm config"""
        return ElementTree.fromstring(vmConfig)

    def getDomain(self, name: str) -> libvirt.virDomain:
        """Lookup domain"""
        try:
            return self._conn.lookupByName(name)
        except libvirt.libvirtError as e:
            raise exceptions.domainNotFound(e) from e

    def refreshPool(self, path: str) -> None:
        """Check if specified path matches an existing
        storage pool and refresh its contents"""
        try:
            pool = self._conn.storagePoolLookupByTargetPath(path)
        except libvirt.libvirtError:
            logging.warning(
                "Restore path [%s] seems not to be an libvirt managed pool, skipping refresh.",
                path,
            )
            return

        try:
            pool.refresh()
            logging.info("Refreshed contents of libvirt pool [%s]", pool.name())
        except libvirt.libvirtError as e:
            logging.warning("Failed to refresh libvirt pool [%s]: [%s]", pool.name(), e)

    @staticmethod
    def blockJobActive(domObj: libvirt.virDomain, disks: List[Any]) -> bool:
        """Check if there is already an active block job for this virtual
        machine, which might block"""
        for disk in disks:
            blockInfo = domObj.blockJobInfo(disk.target)
            if (
                blockInfo
                and blockInfo["type"] == libvirt.VIR_DOMAIN_BLOCK_JOB_TYPE_BACKUP
            ):
                logging.debug("Running block jobs for disk [%s]", disk.target)
                logging.debug(blockInfo)
                return True
        return False

    def hasIncrementalEnabled(self, domObj: libvirt.virDomain) -> bool:
        """Check if virtual machine has enabled required capabilities
        for incremental backup

        Libvirt version >= 7006000  have the feature enabled
        by default without the domain XML including the capability
        statement.
        """
        if self.libvirtVersion >= 7006000:
            return True

        tree = self._getTree(domObj.XMLDesc(0))
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
    def getDomainConfig(domObj: libvirt.virDomain) -> str:
        """Return Virtual Machine configuration as XML"""
        return domObj.XMLDesc(0)

    def defineDomain(self, vmConfig: bytes) -> bool:
        """Define domain based on restored config"""
        try:
            logging.info("Redefining domain based on adjusted config.")
            self._conn.defineXMLFlags(vmConfig.decode(), 0)
            logging.info("Successfully redefined domain.")
        except libvirt.libvirtError as errmsg:
            log.error("Failed to define domain: [%s]", errmsg)
            return False

        return True

    def getDomainInfo(self, vmConfig: str) -> Dict[str, str]:
        """Return object with general vm information relevant
        for backup"""
        tree = self._getTree(vmConfig)
        settings = {}

        for flag in ["loader", "nvram", "kernel", "initrd"]:
            try:
                settings[flag] = tree.find("os").find(flag).text
            except AttributeError as e:
                logging.debug("No setting [%s] found: %s", flag, e)

        logging.debug("Domain Info: [%s]", settings)
        return settings

    def adjustDomainConfigRemoveDisk(self, vmConfig: str, excluded) -> str:
        """Remove disk from config, in case it has been excluded
        from the backup."""
        tree = self._getTree(vmConfig)
        logging.info("Removing excluded disk [%s] from vm config.", excluded)
        try:
            target = tree.xpath(f"devices/disk/target[@dev='{excluded}']")[0]
            disk = target.getparent()
            disk.getparent().remove(disk)
        except IndexError:
            logging.warning(
                "Removing excluded disk from config failed: no object found."
            )

        return ElementTree.tostring(tree, encoding="utf8", method="xml")

    def adjustDomainConfig(
        self, args: Namespace, restoreDisk: DomainDisk, vmConfig: str, targetFile: str
    ) -> str:
        """Adjust virtual machine configuration after restoring. Changes
        the pathes to the virtual machine disks and attempts to remove
        components excluded during restore."""
        tree = self._getTree(vmConfig)

        try:
            logging.info("Removing uuid setting from vm config.")
            uuid = tree.xpath("uuid")[0]
            tree.remove(uuid)
        except IndexError:
            pass

        name = tree.xpath("name")[0]
        if args.name is None:
            domainName = f"restore_{name.text}"
        else:
            domainName = args.name
        logging.info("Changing name from [%s] to [%s]", name.text, domainName)
        name.text = domainName

        for disk in tree.xpath("devices/disk"):
            dev = disk.xpath("target")[0].get("dev")
            originalFile = disk.xpath("source")[0].get("file")
            if dev == restoreDisk.target:
                logging.info(
                    "Change target file for disk [%s] from [%s] to [%s]",
                    restoreDisk.target,
                    originalFile,
                    targetFile,
                )
                disk.xpath("source")[0].set("file", targetFile)
            device = disk.get("device")
            driver = disk.xpath("driver")[0].get("type")
            if device in ("lun", "cdrom", "floppy"):
                logging.info("Removing [%s] device from vm config", device)
                disk.getparent().remove(disk)
                continue
            if driver == "raw" and args.raw is False:
                log.warning(
                    "Removing raw disk [%s] from vm config.",
                    dev,
                )
                disk.getparent().remove(disk)
                continue
            backingStore = disk.xpath("backingStore")
            if backingStore:
                logging.info("Removing existant backing store settings")
                disk.remove(backingStore[0])

        return ElementTree.tostring(tree, encoding="utf8", method="xml")

    @staticmethod
    def getBackingStores(disk: _Element) -> List[Any]:
        """Get list of backing store files defined for disk, usually
        the case if virtual machine has external snapshots."""
        backingStoreFiles = []
        backingStore = disk.find("backingStore")
        while backingStore is not None:
            backingStoreSource = backingStore.find("source")

            if backingStoreSource is not None:
                backingStoreFiles.append(backingStoreSource.get("file"))

            if backingStore.find("backingStore") is not None:
                backingStore = backingStore.find("backingStore")
            else:
                backingStore = None

        return backingStoreFiles

    def getDomainDisks(self, args: Namespace, vmConfig: str) -> List[Any]:
        """Parse virtual machine configuration for disk devices, filter
        all non supported devices
        """
        tree = self._getTree(vmConfig)
        devices = []

        excludeList = None
        if args.exclude is not None:
            excludeList = args.exclude.split(",")

        for disk in tree.xpath("devices/disk"):
            dev = disk.xpath("target")[0].get("dev")

            if excludeList is not None and dev in excludeList:
                log.warning("Excluding Disks %s from backup as requested", dev)
                continue

            # ignore attached lun or direct access block devices
            if disk.xpath("target")[0].get("type") == "block":
                log.warning(
                    "Ignoring device %s does not support changed block tracking.", dev
                )
                continue

            device = disk.get("device")
            if device == "lun":
                log.warning(
                    "Skipping direct attached lun [%s]: does not support changed block tracking.",
                    dev,
                )
                continue
            if device in ("cdrom", "floppy"):
                log.info("Skipping attached [%s] device: [%s].", device, dev)
                continue

            # ignore disk which use raw format, they do not support CBT
            diskFormat = disk.xpath("driver")[0].get("type")
            if diskFormat == "raw" and args.raw is False:
                log.warning(
                    "Raw disk [%s] excluded by default, use option --raw to include.",
                    dev,
                )
                continue

            # attempt to get original disk file name
            diskSrc = disk.xpath("source")[0].get("file")
            diskFileName = os.path.basename(diskSrc)
            diskPath = diskSrc

            if args.include is not None and dev != args.include:
                log.info(
                    "Skipping disk: [%s] as requested: does not match disk [%s]",
                    dev,
                    args.include,
                )
                continue

            backingStoreFiles = self.getBackingStores(disk)

            devices.append(
                DomainDisk(dev, diskFormat, diskFileName, diskPath, backingStoreFiles)
            )

        return devices

    @staticmethod
    def _indentXml(top: _Element) -> str:
        """Indent xml output for debug logging"""
        try:
            ElementTree.indent(top)
        except ElementTree.ParseError as errmsg:
            log.debug("Failed to parse xml: [%s]", errmsg)
        except AttributeError:
            # older ElementTree verisons dont have the
            # indent method, skip silently and use
            # non formatted string
            pass

        xml = ElementTree.tostring(top).decode()
        log.debug("\n%s", xml)

        return xml

    def _createBackupXml(self, args: Namespace, diskList) -> str:
        """Create XML file for starting an backup task using libvirt API."""
        top = ElementTree.Element("domainbackup", {"mode": "pull"})
        if self.remoteHost is None:
            ElementTree.SubElement(
                top, "server", {"transport": "unix", "socket": f"{args.socketfile}"}
            )
        else:
            listen = self.remoteHost
            tls = "no"
            if args.tls:
                tls = "yes"
            if args.nbd_ip is not None:
                listen = args.nbd_ip
            ElementTree.SubElement(
                top,
                "server",
                {"tls": f"{tls}", "name": f"{listen}", "port": f"{args.nbd_port}"},
            )

        disks = ElementTree.SubElement(top, "disks")

        if args.cpt.parent is not False:
            inc = ElementTree.SubElement(top, "incremental")
            inc.text = args.cpt.parent

        for disk in diskList:
            scratchId = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=5)
            )
            scratchFile = f"{args.scratchdir}/backup.{scratchId}.{disk.target}"
            log.debug("Using scratch file: %s", scratchFile)
            dE = ElementTree.SubElement(disks, "disk", {"name": disk.target})
            ElementTree.SubElement(dE, "scratch", {"file": f"{scratchFile}"})

        xml = self._indentXml(top)

        return xml

    def _createCheckpointXml(
        self, diskList: List[Any], parentCheckpoint: str, checkpointName: str
    ) -> str:
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
            if disk.format != "raw":
                ElementTree.SubElement(disks, "disk", {"name": disk.target})

        xml = self._indentXml(top)

        return xml

    @staticmethod
    def fsFreeze(domObj: libvirt.virDomain, mountpoints: None) -> bool:
        """Attempt to freeze domain filesystems using qemu guest agent"""
        log.debug("Attempting to freeze filesystems.")
        try:
            if mountpoints is not None:
                frozen = domObj.fsFreeze(mountpoints.split(","))
            else:
                frozen = domObj.fsFreeze()
            log.info("Freezed [%s] filesystems.", frozen)
            return True
        except libvirt.libvirtError as errmsg:
            log.warning(errmsg)
            return False

    @staticmethod
    def fsThaw(domObj: libvirt.virDomain) -> bool:
        """Thaw freeze filesystems"""
        log.debug("Attempting to thaw filesystems.")
        try:
            thawed = domObj.fsThaw()
            log.info("Thawed [%s] filesystems.", thawed)
            return True
        except libvirt.libvirtError as errmsg:
            log.warning(errmsg)
            return False

    def startBackup(
        self,
        args: Namespace,
        domObj: libvirt.virDomain,
        diskList: List[Any],
    ) -> None:
        """Attempt to start pull based backup task using  XML description"""
        backupXml = self._createBackupXml(args, diskList)
        checkpointXml = None
        freezed = False

        # do not create checkpoint during copy/diff backup.
        # backup saves delta until the last checkpoint
        if args.level not in ("copy", "diff"):
            checkpointXml = self._createCheckpointXml(
                diskList, args.cpt.parent, args.cpt.name
            )
        freezed = self.fsFreeze(domObj, args.freeze_mountpoint)
        try:
            log.debug("Starting backup job via libvirt API.")
            domObj.backupBegin(backupXml, checkpointXml)
            log.debug("Started backup job via libvirt API.")
        except libvirt.libvirtError as errmsg:
            raise exceptions.startBackupFailed(f"Failed to start backup: [{errmsg}]")
        except Exception as e:
            raise exceptions.startBackupFailed(
                f"Unknown exception during backup start: [{e}]"
            )
        finally:
            # check if filesystem is freezed and thaw
            # in case creating checkpoint fails.
            if freezed is True:
                self.fsThaw(domObj)

    @staticmethod
    def checkpointExists(
        domObj: libvirt.virDomain, checkpointName: str
    ) -> libvirt.virDomainCheckpoint:
        """Check if an checkpoint exists"""
        return domObj.checkpointLookupByName(checkpointName)

    @staticmethod
    def getCheckpointXml(cptObj: libvirt.virDomainCheckpoint) -> str:
        """Get Checkpoint XML including size, if possible. Flag
        is not supported amongst all libvirt versions."""
        try:
            return cptObj.getXMLDesc(libvirt.VIR_DOMAIN_CHECKPOINT_XML_SIZE)
        except libvirt.libvirtError as e:
            logging.warning(
                "Failed to get checkpoint info with size information: [%s]", e
            )
            return cptObj.getXMLDesc()

    def getCheckpointSize(self, domObj: libvirt.virDomain, checkpointName: str) -> int:
        """Return current size of checkpoint for all disks"""
        size = 0
        cpt = self.checkpointExists(domObj, checkpointName)
        cptTree = self._getTree(self.getCheckpointXml(cpt))
        for s in cptTree.xpath("disks/disk/@size"):
            size += int(s)

        return size

    def removeAllCheckpoints(
        self,
        domObj: libvirt.virDomain,
        checkpointList: List[Any],
        args: Namespace,
        defaultCheckpointName: str,
    ) -> bool:
        """Remove all existing checkpoints for a virtual machine,
        used during FULL backup to reset checkpoint chain
        """
        log.debug("Cleaning up persistent storage %s", args.checkpointdir)
        try:
            for checkpointFile in glob.glob(f"{args.checkpointdir}/*.xml"):
                log.debug("Remove checkpoint file: %s", checkpointFile)
                os.remove(checkpointFile)
        except OSError as e:
            log.error(
                "Failed to clean persistent storage %s: %s", args.checkpointdir, e
            )
            return False

        if checkpointList is None:
            cpts = domObj.listAllCheckpoints()
            if cpts:
                for cpt in cpts:
                    if self._deleteCheckpoint(cpt, defaultCheckpointName) is False:
                        return False
            return True

        for checkpoint in checkpointList:
            cptObj = self.checkpointExists(domObj, checkpoint)
            if cptObj:
                if self._deleteCheckpoint(cptObj, defaultCheckpointName) is False:
                    return False
        return True

    @staticmethod
    def _deleteCheckpoint(
        cptObj: libvirt.virDomainCheckpoint, defaultCheckpointName: str
    ) -> bool:
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

    @staticmethod
    def stopBackup(domObj: libvirt.virDomain) -> bool:
        """Cancel the backup task using job abort"""
        try:
            domObj.abortJob()
            return True
        except libvirt.libvirtError as err:
            log.warning("Failed to stop backup job: [%s]", err)
            return False

    def redefineCheckpoints(self, domObj: libvirt.virDomain, args: Namespace) -> bool:
        """Redefine checkpoints from persistent storage"""
        log.info("Loading checkpoint list from: [%s]", args.checkpointdir)
        checkpointList = glob.glob(f"{args.checkpointdir}/*.xml")
        checkpointList.sort(key=os.path.getmtime)

        for checkpointFile in checkpointList:
            log.debug("Loading checkpoint config from: [%s]", checkpointFile)
            try:
                with outputhelper.openfile(checkpointFile, "rb") as f:
                    checkpointConfig = f.read()
                    root = ElementTree.fromstring(checkpointConfig)
            except outputhelper.exceptions.OutputException as e:
                log.error("Opening checkpoint file failed: [%s]: %s", checkpointFile, e)
                return False
            except ElementTree.ParseError as e:
                log.error(
                    "Failed to load checkpoint config from [%s]: %s", checkpointFile, e
                )
                return False

            try:
                checkpointName = root.find("name").text
            except ElementTree.ParseError as e:
                log.error("Failed to find checkpoint name: [%s]", e)
                return False

            try:
                _ = self.checkpointExists(domObj, checkpointName)
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
                    checkpointConfig.decode(),
                    libvirt.VIR_DOMAIN_CHECKPOINT_CREATE_REDEFINE,
                )
            except libvirt.libvirtError as e:
                log.error("Redefining checkpoint failed: [%s]: %s", checkpointName, e)
                return False

        return True

    def backupCheckpoint(self, args: Namespace, domObj: libvirt.virDomain) -> bool:
        """save checkpoint config to persistent storage"""
        checkpointFile = f"{args.checkpointdir}/{args.cpt.name}.xml"
        log.info("Saving checkpoint config to: [%s]", checkpointFile)
        try:
            with outputhelper.openfile(checkpointFile, "wb") as f:
                c = self.checkpointExists(domObj, args.cpt.name)
                f.write(self.getCheckpointXml(c).encode())
                return True
        except outputhelper.exceptions.OutputException as errmsg:
            log.error(
                "Failed to save checkpoint config to file: [%s]: %s",
                checkpointFile,
                errmsg,
            )
            return False

    @staticmethod
    def hasforeignCheckpoint(
        domObj: libvirt.virDomain, defaultCheckpointName: str
    ) -> Optional[str]:
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
                log.debug("Found foreign checkpoint: [%s]", checkpointName)
                if defaultCheckpointName not in checkpointName:
                    return checkpointName
        return None
