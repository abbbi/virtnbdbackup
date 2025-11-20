#!/usr/bin/python3
"""
Copyright (C) 2023 Michael Ablassmeier <abi@grinser.de>

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
import tempfile
import logging
from argparse import Namespace
from libvirtnbdbackup import output
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.objects import DomainDisk
from libvirtnbdbackup.virt import xml
from libvirtnbdbackup.virt import disktype


def read(ConfigFile: str) -> str:
    """Read saved virtual machine config'"""
    try:
        return output.openfile(ConfigFile, "rb").read().decode()
    except:
        logging.error("Can't read config file: [%s]", ConfigFile)
        raise


def changeVolumePathes(args: Namespace, vmConfig: str) -> bytes:
    """In case a virtual machine is using the volume based notation to
    configure disks, parsing the disk list from the configuration will
    fail because the volume is not existent anymore. Modify the disk
    setting from volume to file based before continuing to detect the
    attached disks. (#280)
    """
    tree = xml.asTree(vmConfig)
    for disk in tree.xpath("devices/disk"):
        dev = disk.xpath("target")[0].get("dev")
        diskType = disk.get("type")
        if diskType == "volume":
            source = disk.xpath("source")[0]
            disk.set("type", "file")
            volume = source.get("volume")
            volume = os.path.join(args.output, volume)
            source.set("file", volume)
            for attr in ["pool", "volume"]:
                source.attrib.pop(attr, None)
            logging.warning(
                "Disk [%s]: is using volume notation, overriding setting to [%s]",
                dev,
                volume,
            )

    return xml.ElementTree.tostring(tree, encoding="utf8", method="xml")


def removeDisk(vmConfig: str, excluded) -> bytes:
    """Remove disk from config, in case it has been excluded
    from the backup."""
    tree = xml.asTree(vmConfig)
    logging.info("Removing excluded disk [%s] from vm config.", excluded)
    try:
        target = tree.xpath(f"devices/disk/target[@dev='{excluded}']")[0]
        disk = target.getparent()
        disk.getparent().remove(disk)
    except IndexError:
        logging.warning("Removing excluded disk from config failed: no object found.")

    return xml.ElementTree.tostring(tree, encoding="utf8", method="xml")


def removeUuid(vmConfig: str) -> bytes:
    """Remove the auto generated UUID from the config file to allow
    for restore into new name"""
    tree = xml.asTree(vmConfig)
    try:
        logging.info("Removing uuid setting from vm config.")
        uuid = tree.xpath("uuid")[0]
        tree.remove(uuid)
    except IndexError:
        pass

    return xml.ElementTree.tostring(tree, encoding="utf8", method="xml")


def setVMName(args: Namespace, vmConfig: str) -> bytes:
    """Change / set the VM name to be restored"""
    tree = xml.asTree(vmConfig)
    name = tree.xpath("name")[0]
    if args.name is None and not name.text.startswith("restore"):
        domainName = f"restore_{name.text}"
        logging.info("Change VM name from [%s] to [%s]", name.text, domainName)
        name.text = domainName
    else:
        logging.info("Set name from [%s] to [%s]", name.text, args.name)
        name.text = args.name

    return xml.ElementTree.tostring(tree, encoding="utf8", method="xml")


def adjust(args, disk, vmConfig: str, adjustTarget: str) -> bytes:
    """
    Adjust the provided libvirt VM XML (vmConfig) to point the given `disk`
    (matched by its target dev, e.g. vda) at `adjustTarget`.

    RBD target ("rbd:<pool>/<image>"):
      <disk type='network' device='disk'>
        <driver name='qemu' type='raw'/>
        <source protocol='rbd' name='pool/image'/>
        [<auth username='...'><secret type='ceph' uuid='...'/></auth>]
        <target dev='vda' bus='virtio'/>
      </disk>

    File target (/path/to/file):
      <disk type='file' device='disk'>
        <driver name='qemu' type='qcow2|raw'/>  (left as-is unless absent)
        <source file='/path/to/file'/>
      </disk>

    If args.detach_unrestored is True AND args.disk is set, all other <disk> entries
    are removed so the clone never references original images.

    Additionally, we de-duplicate: any non-selected disk that ends up pointing to the
    same RBD pool/image as the selected disk is removed.
    """
    tree = xml.asTree(vmConfig)
    want_rbd = isinstance(adjustTarget, str) and adjustTarget.startswith("rbd:")

    rbd_user = getattr(args, "rbd_user", None)
    rbd_secret_uuid = getattr(args, "rbd_secret_uuid", None)
    target_name = getattr(disk, "target", None)

    def _target_dev(disk_el):
        tgt = disk_el.find("target")
        return tgt.get("dev") if tgt is not None else None

    devices = tree.find("devices")
    if devices is None:
        # No devices section? return unchanged
        return xml.ElementTree.tostring(tree, encoding="utf-8")

    # Find the selected disk element
    selected = None
    for d in xml.disks(tree):
        if _target_dev(d) == target_name:
            selected = d
            break
    if selected is None:
        # Could not find matching disk; return unchanged
        return xml.ElementTree.tostring(tree, encoding="utf-8")

    # ----- Adjust the selected disk -----
    if want_rbd:
        # Parse rbd:pool/image
        pool_image = adjustTarget.split(":", 1)[1]
        if "/" not in pool_image:
            raise ValueError(f"Invalid RBD target '{adjustTarget}', expected rbd:<pool>/<image>")
        pool, image = pool_image.split("/", 1)

        # Force disk type to network, ensure driver
        selected.set("type", "network")
        if selected.get("device") is None:
            selected.set("device", "disk")

        drv = selected.find("driver")
        if drv is None:
            drv = xml.ElementTree.SubElement(selected, "driver")
        drv.set("name", "qemu")
        if drv.get("type") is None:
            drv.set("type", "raw")

        # Remove all existing <source> and <auth> nodes before creating clean RBD source
        for n in list(selected.findall("source")):
            selected.remove(n)
        for n in list(selected.findall("auth")):
            selected.remove(n)

        src = xml.ElementTree.SubElement(selected, "source")
        src.set("protocol", "rbd")
        src.set("name", f"{pool}/{image}")

        # Optional auth
        if rbd_user or rbd_secret_uuid:
            auth = xml.ElementTree.SubElement(selected, "auth")
            if rbd_user:
                auth.set("username", rbd_user)
            if rbd_secret_uuid:
                secret = xml.ElementTree.SubElement(auth, "secret")
                secret.set("type", "ceph")
                secret.set("uuid", rbd_secret_uuid)

        # De-duplication: remove any other disk that points to the same pool/image
        for d in list(xml.disks(tree)):
            if d is selected:
                continue
            # Check if other disk has an RBD source with same name
            s = d.find("source")
            if s is not None and s.get("protocol") == "rbd" and s.get("name") == f"{pool}/{image}":
                try:
                    devices.remove(d)
                    logging.info("Removed duplicate disk referencing the same RBD [%s/%s].", pool, image)
                except Exception:
                    pass

    else:
        # Filesystem-backed disk
        selected.set("type", "file")
        if selected.get("device") is None:
            selected.set("device", "disk")

        # Remove all existing <source> and <auth> just in case
        for n in list(selected.findall("source")):
            selected.remove(n)
        for n in list(selected.findall("auth")):
            selected.remove(n)

        src = selected.find("source")
        if src is None:
            src = xml.ElementTree.SubElement(selected, "source")
        src.attrib.clear()
        src.set("file", adjustTarget)

    # ----- Optionally detach all other (unrestored) disks -----
    detach_others = bool(getattr(args, "detach_unrestored", False)) and bool(getattr(args, "disk", None))
    if detach_others:
        for d in list(xml.disks(tree)):
            if d is selected:
                continue
            try:
                devices.remove(d)
                logging.info("Detached unrestored disk [%s] from adjusted VM config.", _target_dev(d))
            except Exception:
                pass

    return xml.ElementTree.tostring(tree, encoding="utf-8")

def restore(
    args: Namespace,
    vmConfig: str,
    adjustedConfig: bytes,
    targetFileName: str,
) -> None:
    """Restore either original or adjusted vm configuration
    to new directory"""
    targetFile = os.path.join(args.output, os.path.basename(targetFileName))
    if args.adjust_config is True:
        if args.sshClient:
            with tempfile.NamedTemporaryFile(delete=True) as fh:
                fh.write(adjustedConfig)
                lib.copy(args, fh.name, targetFile)
        else:
            with output.openfile(targetFile, "wb") as cnf:
                cnf.write(adjustedConfig)
            logging.info("Adjusted config placed in: [%s]", targetFile)
        if args.define is False:
            logging.info("Use 'virsh define %s' to define VM", targetFile)
    else:
        lib.copy(args, vmConfig, targetFile)
        logging.info("Copied original vm config to [%s]", targetFile)
        logging.info("Note: virtual machine config must be adjusted manually.")
