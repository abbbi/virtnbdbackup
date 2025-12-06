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
import time
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

        if getattr(args, "user", None) and getattr(args, "password", None):
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
            log.info("Connected to remote host: [%s]", remoteHostname)
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

    def defineDomain(
        self, vmConfig: bytes, autoStart: bool, allowExisting: bool = False
    ) -> bool:
        """Define domain based on restored config.

        When allowExisting=True:
          - If a domain with the same name already exists, do NOT fail—just warn and return True.
          - If autoStart is True, apply autostart to the existing domain.
        """
        # Extract domain name from the XML we'll define
        try:
            tree = xml.asTree(vmConfig.decode())
            name_el = tree.find("name")
            dom_name = name_el.text if name_el is not None else None
        except Exception as e:
            log.error("Failed to parse restored VM config for name: %s", e)
            return False

        # If requested, tolerate existing domains
        if allowExisting and dom_name:
            try:
                existing = self._conn.lookupByName(dom_name)
            except libvirt.libvirtError:
                existing = None

            if existing is not None:
                log.warning(
                    "Domain [%s] already exists; skipping re-definition because --auto-register is enabled.",
                    dom_name,
                )
                if autoStart:
                    self.domainAutoStart(existing)
                return True

        # Normal define path
        try:
            log.info("Redefining domain based on adjusted config.")
            domObj = self._conn.defineXMLFlags(vmConfig.decode(), 0)
            log.info("Successfully redefined domain [%s]", domObj.name())
        except libvirt.libvirtError as errmsg:
            # If allowExisting is set, also tolerate 'already exists' errors that happen mid-define.
            msg = str(errmsg)
            if allowExisting and "already exists" in msg.lower() and dom_name:
                log.warning(
                    "Domain [%s] already exists; continuing because --auto-register is enabled. (%s)",
                    dom_name,
                    msg,
                )
                try:
                    domObj = self._conn.lookupByName(dom_name)
                    if autoStart:
                        self.domainAutoStart(domObj)
                except libvirt.libvirtError:
                    pass
                return True

            log.error("Failed to define domain: [%s]", errmsg)
            return False

        if autoStart:
            self.domainAutoStart(domObj)

        return True

    def getDomainInfo(self, vmConfig: str) -> Dict[str, str]:
        """Return object with general vm information relevant
        for backup"""
        tree = xml.asTree(vmConfig)
        settings: Dict[str, str] = {}

        for flag in ["loader", "nvram", "kernel", "initrd"]:
            try:
                settings[flag] = tree.find("os").find(flag).text  # type: ignore[union-attr]
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

    def _hint(self, dev: str) -> None:
        """Show hint about possibility to reconfigure virtual machine with raw
        devices to support incremental backups"""

        if self.libvirtVersion <= 1010000:
            return

        msg = (
            "Check README on how to adjust virtual machine configuration"
            f" to enable full support for disk: [{dev}]."
        )
        log.warning(msg)

    def getDomainDisks(self, args: Namespace, vmConfig: str) -> List[DomainDisk]:
        """Parse virtual machine configuration for disk devices, filter
        all unsupported or excluded devices
        """
        devices: List[DomainDisk] = []

        excludeList = None
        if args.exclude is not None:
            excludeList = args.exclude.split(",")

        for disk in xml.asTree(vmConfig).xpath("devices/disk"):
            discardOption = None
            dev = disk.xpath("target")[0].get("dev")
            device = disk.get("device")
            diskFormat = disk.xpath("driver")[0].get("type")
            discardOption = disk.xpath("driver")[0].get("discard")

            if excludeList is not None and dev in excludeList:
                log.warning("Excluding disk [%s] from backup as requested", dev)
                continue

            if args.include is not None and dev != args.include:
                log.info(
                    "Skipping disk: [%s] as requested: does not match disk [%s]",
                    dev,
                    args.include,
                )
                continue

            # skip cdrom/floppy devices
            if disktype.Optical(device, dev):
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
                # Direct attached block devices can be qcow formatted.
                # Skip only if format != qcow2 (#264)
                if args.raw is False and disktype.Raw(diskFormat, dev):
                    self._hint(dev)
                    continue
                diskPath = disk.xpath("source")[0].get("dev")
            elif diskType == "network":
                # Support Ceph RBD volumes (network/protocol='rbd') when --raw is used
                log.debug("Disk [%s]: network notation", dev)
                src = disk.xpath("source")[0]
                protocol = src.get("protocol")
                # Only handle RBD here; other network protocols are not supported
                if protocol != "rbd":
                    log.info(
                        "Skipping network disk [%s]: unsupported protocol [%s]",
                        dev,
                        protocol,
                    )
                    continue
                if args.raw is False:
                    # RBD presents as driver type='raw' — include only when --raw is set.
                    self._hint(dev)
                    log.info("Skipping RBD disk [%s] (use --raw to include)", dev)
                    continue
                # Expect name="pool/image" on <source>
                name = src.get("name")
                if not name or "/" not in name:
                    log.error("Invalid RBD source 'name' for disk [%s]", dev)
                    continue
                # Synthesize a 'path' so downstream logic has a stable identifier
                diskPath = f"rbd:{name}"
            else:
                log.error("Unable to detect disk volume type for disk [%s]", dev)
                continue

            if diskPath is None:
                log.error("Unable to detect disk source for disk [%s]", dev)
                continue

            # skip direct attached devices if no --raw option is enabled
            if args.raw is False and (
                disktype.Block(disk, dev)
                or disktype.Lun(device, dev)
                or disktype.Raw(diskFormat, dev)
            ):
                self._hint(dev)
                continue

            diskFileName = os.path.basename(diskPath)
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

    def _createBackupXml(self, args: Namespace, diskList: List[DomainDisk]) -> str:
        """Create XML file for starting an backup task using libvirt API."""
        top = xml.ElementTree.Element("domainbackup", {"mode": "pull"})
        if self.remoteHost == "":
            xml.ElementTree.SubElement(
                top, "server", {"transport": "unix", "socket": f"{args.socketfile}"}
            )
        else:
            listen = self.remoteHost
            tls = "no"
            if getattr(args, "tls", False):
                tls = "yes"
            if getattr(args, "nbd_ip", "") != "":
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

        for d in diskList:
            scratchId = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=5)
            )
            scratchFile = f"{args.scratchdir}/backup.{scratchId}.{d.target}"
            log.debug("Using scratch file: %s", scratchFile)
            dE = xml.ElementTree.SubElement(disks, "disk", {"name": d.target})
            xml.ElementTree.SubElement(dE, "scratch", {"file": f"{scratchFile}"})

        return xml.indent(top)

    def _createCheckpointXml(
        self, diskList: List[DomainDisk], parentCheckpoint: str, checkpointName: str
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
        for d in diskList:
            # No persistent checkpoint will be created for raw disks,
            # because it is not supported. Backup will only be crash
            # consistent.
            if d.format != "raw":
                xml.ElementTree.SubElement(disks, "disk", {"name": d.target})

        return xml.indent(top)
        
    def ensureDomainStopped(self, name: str, graceful_timeout: int = 60) -> bool:
        """
        Ensure the domain 'name' is not running.
        1) Attempt graceful ACPI shutdown and wait up to 'graceful_timeout' seconds.
        2) If still running, force poweroff (destroy).
        Returns True if the domain is stopped or does not exist; False on failure.
        """
        try:
            dom = self.getDomain(name)
        except domainNotFound:
            # Domain with that name isn't defined -> nothing to stop.
            return True

        try:
            if not dom.isActive():
                return True
        except libvirt.libvirtError as e:
            log.warning("Failed to check domain state for [%s]: %s", name, e)
            # Try to proceed anyway

        # 1) Graceful shutdown
        try:
            log.info("Requesting graceful shutdown of domain [%s]...", name)
            dom.shutdown()
        except libvirt.libvirtError as e:
            log.warning("Graceful shutdown request failed for [%s]: %s", name, e)

        deadline = time.time() + graceful_timeout
        while time.time() < deadline:
            try:
                if not dom.isActive():
                    log.info("Domain [%s] shut down gracefully.", name)
                    return True
            except libvirt.libvirtError:
                # If we can't query state, give it a moment
                pass
            time.sleep(1)

        # 2) Force poweroff
        log.warning("Graceful shutdown timed out for [%s]; forcing poweroff.", name)
        try:
            dom.destroy()
        except libvirt.libvirtError as e:
            log.error("Force poweroff failed for [%s]: %s", name, e)
            return False

        # Confirm it’s off
        for _ in range(30):
            try:
                if not dom.isActive():
                    log.info("Domain [%s] is now stopped.", name)
                    return True
            except libvirt.libvirtError:
                pass
            time.sleep(0.5)

        log.error("Domain [%s] still appears to be running after destroy().", name)
        return False    

    def startBackup(
        self,
        args: Namespace,
        domObj: libvirt.virDomain,
        diskList: List[DomainDisk],
    ) -> None:
        """Attempt to start pull based backup task using XML description"""
        backupXml = self._createBackupXml(args, diskList)
        checkpointXml = None
        freezed = False
        flags = 0

        try:
            flags = libvirt.VIR_DOMAIN_BACKUP_BEGIN_PRESERVE_SHUTDOWN_DOMAIN
            log.info("Setting supported flag to prevent vm shutdown during backup.")
        except AttributeError:
            pass

        # do not create checkpoint during copy/diff backup.
        # backup saves delta until the last checkpoint
        if args.level not in ("copy", "diff"):
            checkpointXml = self._createCheckpointXml(
                diskList, args.cpt.parent, args.cpt.name
            )
        freezed = fs.freeze(domObj, args.freeze_mountpoint)
        try:
            log.debug("Starting backup job via libvirt API.")
            domObj.backupBegin(backupXml, checkpointXml, flags)
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

