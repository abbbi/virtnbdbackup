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
import json
import logging
from argparse import Namespace
from typing import Optional, Union, Any, List
from lxml import etree as ElementTree
import libvirt
from libvirtnbdbackup import output
from libvirtnbdbackup.virt import xml
from libvirtnbdbackup.output.exceptions import OutputException
from libvirtnbdbackup.common import defaultCheckpointName
from libvirtnbdbackup.exceptions import (
    NoCheckpointsFound,
    ReadCheckpointsError,
    CheckpointException,
    SaveCheckpointError,
    ForeignCeckpointError,
    RedefineCheckpointError,
    RemoveCheckpointError,
)

log = logging.getLogger()

redefineFlags = (
    libvirt.VIR_DOMAIN_CHECKPOINT_CREATE_REDEFINE
    | libvirt.VIR_DOMAIN_CHECKPOINT_CREATE_REDEFINE_VALIDATE
)


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
    size: int = 0
    cpt = exists(domObj, checkpointName)
    cptTree = xml.asTree(getXml(cpt))
    for s in cptTree.xpath("disks/disk/@size"):
        size += int(s)

    return size


def delete(
    domObj: libvirt.virDomain, cptObj: libvirt.virDomainCheckpoint, checkpointName: str
) -> bool:
    """Delete checkpoint or checkpoint metadata in case validation
    fails (bitmap is missing, but checkpoint still existent)"""
    flags: int = 0
    checkpointName = cptObj.getName()
    if defaultCheckpointName not in checkpointName:
        log.debug(
            "Skipping checkpoint removal: [%s]: not from this application",
            checkpointName,
        )
        return True
    log.debug("Attempt to remove checkpoint: [%s]", checkpointName)

    if not validate(domObj, checkpointName):
        log.warning(
            "Checkpoint inconsistency detected, removing metadata for checkpoint."
        )
        flags = libvirt.VIR_DOMAIN_CHECKPOINT_DELETE_METADATA_ONLY

    try:
        cptObj.delete(flags)
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


def _hasForeign(domObj: libvirt.virDomain, checkpointName: str) -> Optional[str]:
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
    if not cpts:
        return None

    for cpt in cpts:
        checkpointName = cpt.getName()
        log.debug("Found foreign checkpoint: [%s]", checkpointName)
        if defaultCheckpointName not in checkpointName:
            return checkpointName

    return None


def checkForeign(
    args: Namespace,
    domObj: libvirt.virDomain,
) -> bool:
    """Check and warn user if virtual machine has checkpoints
    not originating from this utility"""
    foreign = None
    if args.level in ("full", "inc", "diff"):
        foreign = _hasForeign(domObj, defaultCheckpointName)

    if not foreign:
        return True

    log.fatal("Foreign checkpoint found: [%s]", foreign)
    log.fatal("This checkpoint has not been created by this utility.")
    log.fatal(
        "To ensure backup chain consistency, "
        "remove existing checkpoints "
        "and start a new backup chain by creating a full backup."
    )

    raise ForeignCeckpointError


def removeAll(
    domObj: libvirt.virDomain,
    checkpointList: Union[List[Any], None],
    args: Namespace,
    checkpointName: str,
) -> bool:
    """Remove all existing checkpoints for a virtual machine,
    used during FULL backup to reset checkpoint chain
    """
    log.debug("Cleaning up persistent storage %s", args.checkpointdir)
    log.info("Removing all existent checkpoints before full backup.")
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
                if delete(domObj, cpt, checkpointName) is False:
                    return False
        return True

    for cp in checkpointList:
        cptObj = exists(domObj, cp)
        if cptObj:
            if delete(domObj, cptObj, checkpointName) is False:
                return False
    return True


def redefine(domObj: libvirt.virDomain, args: Namespace) -> bool:
    """Redefine checkpoints from persistent storage"""
    checkpointList = glob.glob(f"{args.checkpointdir}/*.xml")
    checkpointList.sort(key=os.path.getmtime)

    if checkpointList:
        log.info("Loaded checkpoint list from: [%s]", args.checkpointdir)

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
                redefineFlags,
            )
        except libvirt.libvirtError as e:
            log.error("Redefining checkpoint failed: [%s]: %s", checkpointName, e)
            return False

    return True


def read(cFile: str) -> List[str]:
    """Open checkpoint file and read checkpoint
    information"""
    checkpoints: List[str] = []
    if not os.path.exists(cFile):
        return checkpoints

    try:
        with output.openfile(cFile, "rb") as fh:
            checkpoints = json.loads(fh.read().decode())
        return checkpoints
    except OutputException as e:
        raise ReadCheckpointsError(f"Failed to read checkpoint file: [{e}]") from e
    except json.decoder.JSONDecodeError as e:
        raise ReadCheckpointsError(f"Invalid checkpoint file: [{e}]") from e


def save(args: Namespace) -> None:
    """Append created checkpoint to checkpoint
    file"""
    try:
        checkpoints = read(args.cpt.file)
        checkpoints.append(args.cpt.name)
        with output.openfile(args.cpt.file, "wb") as cFw:
            cFw.write(json.dumps(checkpoints).encode())
    except CheckpointException as e:
        raise CheckpointException from e
    except OutputException as e:
        raise SaveCheckpointError from e


def validate(domObj: libvirt.virDomain, checkpointName: str) -> bool:
    """Validate that checkpoint and bitmap exist and are OK
    Currently the only way to correctly verify consistency is by redefine the checkpoint with
    VIR_DOMAIN_CHECKPOINT_CREATE_REDEFINE_VALIDATE option set, which will check the bitmap
    consistency, too."""
    try:
        c = domObj.checkpointLookupByName(checkpointName)
        checkpointXml = c.getXMLDesc(0)

        # Redefine the checkpoint using the provided XML description
        if not domObj.checkpointCreateXML(checkpointXml, redefineFlags):
            return False
        return True
    except libvirt.libvirtError as e:
        log.warning("Failed to validate checkpoint: [%s]", e)
        return False


def create(
    args: Namespace,
    domObj: libvirt.virDomain,
) -> None:
    """Checkpoint handling for different backup modes
    to be executed. Create, check and redefine checkpoints based
    on backup mode.

    Creates a new namespace in the argparse object,
    for easy pass around in further functions.
    """
    checkpointName: str = f"{defaultCheckpointName}.0"
    parentCheckpoint: str = ""
    cptFile: str = f"{args.output}/{args.domain}.cpt"

    checkpoints: List[str] = read(cptFile)
    log.info("Loaded checkpoints from: [%s]", cptFile)

    if args.offline is False:
        if redefine(domObj, args) is False:
            raise RedefineCheckpointError("Failed to redefine checkpoints.")

    # save level to reuse it properly when filename is selected for the backup
    args.level_filename = args.level

    log.info("Checkpoint handling.")
    if args.level == "full" and checkpoints:
        if not removeAll(domObj, checkpoints, args, defaultCheckpointName):
            raise RemoveCheckpointError("Failed to remove checkpoint.")
        os.remove(cptFile)
        checkpoints = []
    elif args.level == "full" and len(checkpoints) < 1:
        if not removeAll(domObj, None, args, defaultCheckpointName):
            raise RemoveCheckpointError("Failed to remove checkpoint.")
        checkpoints = []

    if checkpoints and args.level in ("inc", "diff"):
        nextCpt = len(checkpoints)
        checkpointName = f"{defaultCheckpointName}.{nextCpt}"
        parentCheckpoint = checkpoints[-1]
        log.info("Next checkpoint id: [%s].", nextCpt)
        log.info("Parent checkpoint name [%s].", parentCheckpoint)

        if args.offline is True:
            log.info("Offline backup, using latest checkpoint, saving only delta.")
            checkpointName = parentCheckpoint

        # Autostart is disabled, validation could not be performed
        elif not validate(domObj, parentCheckpoint):
            log.warning(
                "Checkpoint [%s] is invalid, switching backup to full.",
                parentCheckpoint,
            )
            args.level = "full"
            # reset back to defaults
            parentCheckpoint = ""

    if args.level in ("inc", "diff") and len(checkpoints) < 1:
        raise NoCheckpointsFound(
            "No existing checkpoints found, execute full backup first."
        )

    if args.level == "diff":
        log.info("Diff backup: saving delta since checkpoint: [%s].", parentCheckpoint)

    if args.level in ("full", "inc"):
        log.info("Using checkpoint name: [%s].", checkpointName)

    args.cpt = Namespace()
    args.cpt.name = checkpointName
    args.cpt.parent = parentCheckpoint
    args.cpt.file = cptFile

    log.debug("Checkpoint info: [%s].", vars(args.cpt))
