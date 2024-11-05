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


def setVMName(args: Namespace, vmConfig: bytes) -> bytes:
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


def adjust(restoreDisk: DomainDisk, vmConfig: str, targetFile: str) -> bytes:
    """Adjust virtual machine configuration after restoring. Changes
    the paths to the virtual machine disks and attempts to remove
    components excluded during restore."""
    tree = xml.asTree(vmConfig)
    for disk in tree.xpath("devices/disk"):
        if disk.get("type") == "volume":
            logging.info("Disk has type volume, resetting to type file.")
            disk.set("type", "file")

        dev = disk.xpath("target")[0].get("dev")
        logging.debug("Handling target device: [%s]", dev)

        device = disk.get("device")
        driver = disk.xpath("driver")[0].get("type")

        if disktype.Optical(device, dev):
            logging.info("Removing device [%s], type [%s] from vm config", dev, device)
            disk.getparent().remove(disk)
            continue

        if disktype.Raw(driver, device):
            logging.warning(
                "Removing raw disk [%s] from vm config, use --raw to copy as is.",
                dev,
            )
            disk.getparent().remove(disk)
            continue
        backingStore = disk.xpath("backingStore")
        if backingStore:
            logging.info("Removing existent backing store settings")
            disk.remove(backingStore[0])

        originalFile = disk.xpath("source")[0].get("file")
        if dev == restoreDisk.target:
            abspath = os.path.abspath(targetFile)
            logging.info(
                "Change target file for disk [%s] from [%s] to [%s]",
                restoreDisk.target,
                originalFile,
                abspath,
            )
            disk.xpath("source")[0].set("file", abspath)

    return xml.ElementTree.tostring(tree, encoding="utf8", method="xml")


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
