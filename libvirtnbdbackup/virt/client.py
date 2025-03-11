"""
Copyright (C) 2023  Michael Ablassmeier <abi@grinser.de>

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
import logging
from argparse import Namespace
from typing import Any, Dict, List, Tuple, Union
import libvirt
from libvirtnbdbackup.objects import DomainDisk
from libvirtnbdbackup.virt.exceptions import (
    domainNotFound,
    connectionFailed,
    startBackupFailed,
)
from libvirtnbdbackup.virt import fs
from libvirtnbdbackup.virt import xml
from libvirtnbdbackup.virt import disktype


def libvirt_ignore(
    _ignore: None, _err: Tuple[int, int, str, int, str, str, None, int, int]
) -> None:
    """this is required so libvirt.py does not report errors to stderr
    which it does by default. Error messages are fetched accordingly
    using exceptions.
    """


libvirt.registerErrorHandler(f=libvirt_ignore, ctx=None)

log = logging.getLogger("virt")


class client:
    """Libvirt related functions"""

    def __init__(self, uri: Namespace) -> None:
        self.remoteHost: str = ""
        self._conn = self._connect(uri)
        self._domObj = None
        self.libvirtVersion = self._conn.getLibVersion()

    @staticmethod
    def _connectAuth(uri: str, user: str, password: str) -> libvirt.virConnect:
        """Use openAuth if connection for advanced SASL authentication mechanisms
        if username and password are set"""

        def _cred(credentials, user_data) -> int:
            for credential in credentials:
                if credential[0] == libvirt.VIR_CRED_AUTHNAME:
                    credential[4] = user_data[0]
                elif credential[0] == libvirt.VIR_CRED_PASSPHRASE:
                    credential[4] = user_data[1]

            return 0

        log.debug("Username: %s", user)
        log.debug("Password: %s", password)

        try:
            flags: List[Any] = [libvirt.VIR_CRED_AUTHNAME, libvirt.VIR_CRED_PASSPHRASE]
            auth: List[Any] = [flags]
            if user is not None and password is not None:
                user_data = [user, password]
                auth.append(_cred)
                auth.append(user_data)

            return libvirt.openAuth(uri, auth, 0)
        except libvirt.libvirtError as e:
            raise connectionFailed(e) from e

    @staticmethod
    def _connectOpen(uri: str) -> libvirt.virConnect:
        """Open connection with regular libvirt URI for local authentication
        without further authentication mechanisms required"""
        try:
            return libvirt.open(uri)
        except libvirt.libvirtError as e:
            if e.get_error_code() == 45:
                errmsg = f"{e}: --user and --password options for SASL authentication are required."
                raise connectionFailed(errmsg) from e
            raise connectionFailed(e) from e

    def _connect(self, args: Namespace) -> libvirt.virConnect:
        """return libvirt connection handle and check if connection
        is established to a remote host."""
        log.debug("Libvirt URI: [%s]", args.uri)

        if args.user and args.password:
            conn = self._connectAuth(args.uri, args.user, args.password)
        else:
            conn = self._connectOpen(args.uri)

        # Detect if we are connected to a remote libvirt daemon by
        # comparing the local and remote hostname. If qemu+ssh is
        # part of the libvirt URI, set the remote host as well.
        # This will spawn the NBD service for data transfer via
        # TCP socket instead of local socket file and related virtual
        # domain files will be copied via SFTP.
        if "qemu+ssh" in args.uri:
            remoteHostname = conn.getHostname()
            log.info(
                "Connected to remote host: [%s]",
                remoteHostname,
            )
            self.remoteHost = remoteHostname

        return conn

    def close(self) -> None:
        """Disconnect"""
        log.debug("Close connection to libvirt.")
        self._conn.close()

    def getDomain(self, name: str) -> libvirt.virDomain:
        """Lookup domain"""
        try:
            return self._conn.lookupByName(name)
        except libvirt.libvirtError as e:
            raise domainNotFound(e) from e

    def refreshPool(self, path: str) -> None:
        """Check if specified path matches an existing
        storage pool and refresh its contents"""
        try:
            pool = self._conn.storagePoolLookupByTargetPath(path)
        except libvirt.libvirtError:
            log.warning(
                "Restore path [%s] seems not to be an libvirt managed pool, skipping refresh.",
                path,
            )
            return

        try:
            pool.refresh()
            log.info("Refreshed contents of libvirt pool [%s]", pool.name())
        except libvirt.libvirtError as e:
            log.warning("Failed to refresh libvirt pool [%s]: [%s]", pool.name(), e)

    @staticmethod
    def blockJobActive(domObj: libvirt.virDomain, disks: List[DomainDisk]) -> bool:
        """Check if there is already an active block job for this virtual
        machine, which might block"""
        for disk in disks:
            blockInfo = domObj.blockJobInfo(disk.target)
            if (
                blockInfo
                and blockInfo["type"] == libvirt.VIR_DOMAIN_BLOCK_JOB_TYPE_BACKUP
            ):
                log.debug("Running block jobs for disk [%s]", disk.target)
                log.debug(blockInfo)
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

        tree = xml.asTree(domObj.XMLDesc(0))
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

    @staticmethod
    def startDomain(domObj: libvirt.virDomain) -> bool:
        """Start virtual machine in paused state to allow full / inc backup"""
        return domObj.createWithFlags(
            flags=libvirt.VIR_DOMAIN_START_PAUSED | libvirt.VIR_DOMAIN_START_AUTODESTROY
        )

    @staticmethod
    def domainAutoStart(domObj: libvirt.virDomain) -> None:
        """Mark virtual machine for autostart"""
        try:
            domObj.setAutostart(1)
            log.info("Setting autostart config for domain.")
        except libvirt.libvirtError as errmsg:
            log.warning("Failed to set autostart flag for domain: [%s]", errmsg)

    def defineDomain(self, vmConfig: bytes, autoStart: bool) -> bool:
        """Define domain based on restored config"""
        try:
            log.info("Redefining domain based on adjusted config.")
            domObj = self._conn.defineXMLFlags(vmConfig.decode(), 0)
            log.info("Successfully redefined domain [%s]", domObj.name())
        except libvirt.libvirtError as errmsg:
            log.error("Failed to define domain: [%s]", errmsg)
            return False

        if autoStart is True:
            self.domainAutoStart(domObj)

        return True

    def getDomainInfo(self, vmConfig: str) -> Dict[str, str]:
        """Return object with general vm information relevant
        for backup"""
        tree = xml.asTree(vmConfig)
        settings = {}

        for flag in ["loader", "nvram", "kernel", "initrd"]:
            try:
                settings[flag] = tree.find("os").find(flag).text
            except AttributeError as e:
                log.debug("No setting [%s] found: %s", flag, e)

        log.debug("Domain Info: [%s]", settings)
        return settings

    def getTPMDevice(self, vmConfig: str) -> bool:
        """Check if virtual machine has configured an emulated (swtpm based) TPM device"""
        tree = xml.asTree(vmConfig)
        device = tree.find("devices/tpm")
        if device is not None:
            tpm = device.xpath("backend")[0].get("type")
            return tpm == "emulator"

        return False

    @staticmethod
    def getBackingStores(disk: xml._Element) -> List[str]:
        """Get list of backing store files defined for disk, usually
        the case if virtual machine has external snapshots."""
        backingStoreFiles: List[str] = []
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

    def _getDiskPathByVolume(self, disk: xml._Element) -> Union[str, None]:
        """If virtual machine disk is configured via type='volume'
        get path to disk via appropriate libvirt functions,
        pool and volume setting are mandatory as by xml schema definition"""
        vol = disk.xpath("source")[0].get("volume")
        pool = disk.xpath("source")[0].get("pool")

        try:
            diskPool = self._conn.storagePoolLookupByName(pool)
            diskPath = diskPool.storageVolLookupByName(vol).path()
        except libvirt.libvirtError as errmsg:
            log.error("Failed to detect vm disk by volumes: [%s]", errmsg)
            return None

        return diskPath

    def getDomainDisks(self, args: Namespace, vmConfig: str) -> List[DomainDisk]:
        """Parse virtual machine configuration for disk devices, filter
        all non supported devices
        """
        tree = xml.asTree(vmConfig)
        devices = []

        excludeList = None
        if args.exclude is not None:
            excludeList = args.exclude.split(",")

        for disk in tree.xpath("devices/disk"):
            discardOption = None
            dev = disk.xpath("target")[0].get("dev")
            device = disk.get("device")
            diskFormat = disk.xpath("driver")[0].get("type")
            discardOption = disk.xpath("driver")[0].get("discard")

            if excludeList is not None and dev in excludeList:
                log.warning("Excluding disk [%s] from backup as requested", dev)
                continue

            # skip cdrom/floppy devices
            if disktype.Optical(device, dev):
                continue

            # include other direct attached devices if --raw option is enabled
            if args.raw is False and (
                disktype.Block(disk, dev)
                or disktype.Lun(device, dev)
                or disktype.Raw(diskFormat, dev)
            ):
                continue

            diskPath = None
            diskType = disk.get("type")
            if diskType == "volume":
                log.debug("Disk [%s]: volume notation", dev)
                diskPath = self._getDiskPathByVolume(disk)
            elif diskType == "file":
                log.debug("Disk [%s]: file notation", dev)
                diskPath = disk.xpath("source")[0].get("file")
            elif diskType == "block":
                if args.raw is False:
                    log.warning(
                        "Skipping direct attached block device [%s], use option --raw to include.",
                        dev,
                    )
                    continue
                diskPath = disk.xpath("source")[0].get("dev")
            else:
                log.error("Unable to detect disk volume type for disk [%s]", dev)
                continue

            if diskPath is None:
                log.error("Unable to detect disk source for disk [%s]", dev)
                continue

            diskFileName = os.path.basename(diskPath)

            if args.include is not None and dev != args.include:
                log.info(
                    "Skipping disk: [%s] as requested: does not match disk [%s]",
                    dev,
                    args.include,
                )
                continue

            backingStoreFiles = self.getBackingStores(disk)

            devices.append(
                DomainDisk(
                    dev,
                    diskFormat,
                    diskFileName,
                    diskPath,
                    backingStoreFiles,
                    discardOption,
                )
            )

        log.debug("Device list: %s ", devices)
        return devices

    def _createBackupXml(self, args: Namespace, diskList) -> str:
        """Create XML file for starting an backup task using libvirt API."""
        top = xml.ElementTree.Element("domainbackup", {"mode": "pull"})
        if self.remoteHost == "":
            xml.ElementTree.SubElement(
                top, "server", {"transport": "unix", "socket": f"{args.socketfile}"}
            )
        else:
            listen = self.remoteHost
            tls = "no"
            if args.tls:
                tls = "yes"
            if args.nbd_ip != "":
                listen = args.nbd_ip
            xml.ElementTree.SubElement(
                top,
                "server",
                {"tls": f"{tls}", "name": f"{listen}", "port": f"{args.nbd_port}"},
            )

        disks = xml.ElementTree.SubElement(top, "disks")

        if args.cpt.parent != "":
            inc = xml.ElementTree.SubElement(top, "incremental")
            inc.text = args.cpt.parent

        for disk in diskList:
            scratchId = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=5)
            )
            scratchFile = f"{args.scratchdir}/backup.{scratchId}.{disk.target}"
            log.debug("Using scratch file: %s", scratchFile)
            dE = xml.ElementTree.SubElement(disks, "disk", {"name": disk.target})
            xml.ElementTree.SubElement(dE, "scratch", {"file": f"{scratchFile}"})

        return xml.indent(top)

    def _createCheckpointXml(
        self, diskList: List[Any], parentCheckpoint: str, checkpointName: str
    ) -> str:
        """Create valid checkpoint XML file which is passed to libvirt API"""
        top = xml.ElementTree.Element("domaincheckpoint")
        desc = xml.ElementTree.SubElement(top, "description")
        desc.text = "Backup checkpoint"
        name = xml.ElementTree.SubElement(top, "name")
        name.text = checkpointName
        if parentCheckpoint != "":
            pct = xml.ElementTree.SubElement(top, "parent")
            cptName = xml.ElementTree.SubElement(pct, "name")
            cptName.text = parentCheckpoint
        disks = xml.ElementTree.SubElement(top, "disks")
        for disk in diskList:
            # No persistent checkpoint will be created for raw disks,
            # because it is not supported. Backup will only be crash
            # consistent. If we would like to create a consistent
            # backup, we would have to create an snapshot for these
            # kind of disks, example:
            # virsh checkpoint-create-as vm4 --diskspec sdb
            # error: unsupported configuration:  \
            # checkpoint for disk sdb unsupported for storage type raw
            # See also:
            # https://lists.gnu.org/archive/html/qemu-devel/2021-03/msg07448.html
            if disk.format != "raw":
                xml.ElementTree.SubElement(disks, "disk", {"name": disk.target})

        return xml.indent(top)

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
        freezed = fs.freeze(domObj, args.freeze_mountpoint)
        try:
            log.debug("Starting backup job via libvirt API.")
            domObj.backupBegin(backupXml, checkpointXml)
            log.debug("Started backup job via libvirt API.")
        except libvirt.libvirtError as errmsg:
            code = errmsg.get_error_code()
            if code == libvirt.VIR_ERR_CHECKPOINT_INCONSISTENT:
                raise startBackupFailed(
                    "Bitmap inconsistency detected: please cleanup checkpoints using virsh "
                    f"and execute new full backup: {errmsg}"
                ) from errmsg
            raise startBackupFailed(f"Failed to start backup: [{errmsg}]") from errmsg
        except Exception as e:
            log.exception(e)
            raise startBackupFailed(
                f"Unknown exception during backup start: [{e}]"
            ) from e
        finally:
            # check if filesystem is freezed and thaw
            # in case creating checkpoint fails.
            if freezed is True:
                fs.thaw(domObj)

    @staticmethod
    def stopBackup(domObj: libvirt.virDomain) -> bool:
        """Cancel the backup task using job abort"""
        try:
            domObj.abortJob()
            return True
        except libvirt.libvirtError as err:
            log.warning("Failed to stop backup job: [%s]", err)
            return False
