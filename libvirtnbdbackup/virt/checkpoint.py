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
import glob
import logging
from argparse import Namespace
from typing import Optional, Union, Any, List
from lxml import etree as ElementTree
import libvirt
from libvirtnbdbackup import output
from libvirtnbdbackup.virt import xml
from libvirtnbdbackup.output.exceptions import OutputException

log = logging.getLogger()


def exists(
    domObj: libvirt.virDomain, checkpointName: str
) -> libvirt.virDomainCheckpoint:
    """Check if an checkpoint exists"""
    return domObj.checkpointLookupByName(checkpointName)


def getXml(cptObj: libvirt.virDomainCheckpoint) -> str:
    """Get Checkpoint XML including size, if possible. Flag
    is not supported amongst all libvirt versions."""
    try:
        return cptObj.getXMLDesc(libvirt.VIR_DOMAIN_CHECKPOINT_XML_SIZE)
    except libvirt.libvirtError as e:
        log.warning("Failed to get checkpoint info with size information: [%s]", e)
        return cptObj.getXMLDesc()


def getSize(domObj: libvirt.virDomain, checkpointName: str) -> int:
    """Return current size of checkpoint for all disks"""
    size = 0
    cpt = exists(domObj, checkpointName)
    cptTree = xml.asTree(getXml(cpt))
    for s in cptTree.xpath("disks/disk/@size"):
        size += int(s)

    return size


def delete(cptObj: libvirt.virDomainCheckpoint, defaultCheckpointName: str) -> bool:
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


def backup(args: Namespace, domObj: libvirt.virDomain) -> bool:
    """save checkpoint config to persistent storage"""
    checkpointFile = f"{args.checkpointdir}/{args.cpt.name}.xml"
    log.info("Saving checkpoint config to: [%s]", checkpointFile)
    try:
        with output.openfile(checkpointFile, "wb") as f:
            c = exists(domObj, args.cpt.name)
            f.write(getXml(c).encode())
            return True
    except OutputException as errmsg:
        log.error(
            "Failed to save checkpoint config to file: [%s]: %s",
            checkpointFile,
            errmsg,
        )
        return False


def hasForeign(domObj: libvirt.virDomain, defaultCheckpointName: str) -> Optional[str]:
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


def removeAll(
    domObj: libvirt.virDomain,
    checkpointList: Union[List[Any], None],
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
        log.error("Failed to clean persistent storage %s: %s", args.checkpointdir, e)
        return False

    if checkpointList is None:
        cpts = domObj.listAllCheckpoints()
        if cpts:
            for cpt in cpts:
                if delete(cpt, defaultCheckpointName) is False:
                    return False
        return True

    for cp in checkpointList:
        cptObj = exists(domObj, cp)
        if cptObj:
            if delete(cptObj, defaultCheckpointName) is False:
                return False
    return True


def redefine(domObj: libvirt.virDomain, args: Namespace) -> bool:
    """Redefine checkpoints from persistent storage"""
    log.info("Loading checkpoint list from: [%s]", args.checkpointdir)
    checkpointList = glob.glob(f"{args.checkpointdir}/*.xml")
    checkpointList.sort(key=os.path.getmtime)

    for checkpointFile in checkpointList:
        log.debug("Loading checkpoint config from: [%s]", checkpointFile)
        try:
            with output.openfile(checkpointFile, "rb") as f:
                checkpointConfig = f.read()
                root = ElementTree.fromstring(checkpointConfig)
        except OutputException as e:
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
            _ = exists(domObj, checkpointName)
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
