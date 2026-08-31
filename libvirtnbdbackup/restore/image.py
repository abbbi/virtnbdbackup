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
import logging
import json
from argparse import ArgumentTypeError, Namespace
from typing import List, Dict
from libvirtnbdbackup.qemu import util as qemu
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.exceptions import RestoreError
from libvirtnbdbackup.qemu.exceptions import ProcessError
from libvirtnbdbackup.output.exceptions import OutputException
from libvirtnbdbackup.ssh.exceptions import sshError


def parseDataFileRelocations(value: str) -> Dict[str, str]:
    """Parse comma-separated disk:data-file relocation mappings."""
    relocations: Dict[str, str] = {}
    for mapping in value.split(","):
        diskName, separator, dataFile = mapping.partition(":")
        diskName = diskName.strip()
        dataFile = dataFile.strip()
        if not separator or not diskName or not dataFile:
            raise ArgumentTypeError(
                "data-file relocations must use DISK:PATH[,DISK:PATH...]"
            )
        if diskName in relocations:
            raise ArgumentTypeError(
                f"duplicate data-file relocation for disk '{diskName}'"
            )
        relocations[diskName] = dataFile

    return relocations


def getConfig(  # pylint: disable=too-many-statements
    args: Namespace, meta: Dict[str, str]
) -> List[str]:
    """Check if backup includes exported qcow config and return a list
    of options passed to qemu-img create command"""
    opt: List[str] = []
    qcowConfig = None
    relocatedDataFile = getattr(args, "relocate_data_file", {}).get(meta["diskName"])
    qcowConfigFile = args.inputSource.list(
        args.input, f"{meta['diskName']}*.qcow.json*", -1
    )
    if not qcowConfigFile:
        if relocatedDataFile:
            raise RestoreError(
                f"Disk [{meta['diskName']}] has no saved QCOW data-file configuration"
            )
        logging.warning(
            "No QCOW image config found in [%s], will use default options.", args.input
        )
        return opt

    lastConfigFile = qcowConfigFile[0]

    try:
        with args.inputSource.open(lastConfigFile, "rb") as qFh:
            qcowConfig = json.loads(qFh.read().decode())
        logging.info("Using QCOW options from backup file: [%s]", lastConfigFile)
    except (
        OutputException,
        json.decoder.JSONDecodeError,
    ) as errmsg:
        if relocatedDataFile:
            raise RestoreError(
                f"Unable to relocate data-file for disk [{meta['diskName']}]: "
                f"failed to load saved QCOW configuration"
            ) from errmsg
        logging.warning(
            "Unable to load original QCOW image config, using defaults: [%s].",
            errmsg,
        )
        return opt

    try:
        opt.append("-o")
        opt.append(f"compat={qcowConfig['format-specific']['data']['compat']}")
    except KeyError as errmsg:
        logging.warning("Unable apply QCOW specific compat option: [%s]", errmsg)

    try:
        opt.append("-o")
        opt.append(f"cluster_size={qcowConfig['cluster-size']}")
    except KeyError as errmsg:
        logging.warning("Unable apply QCOW specific cluster_size option: [%s]", errmsg)

    try:
        if qcowConfig["format-specific"]["data"]["lazy-refcounts"]:
            opt.append("-o")
            opt.append("lazy_refcounts=on")
    except KeyError as errmsg:
        logging.warning(
            "Unable apply QCOW specific lazy_refcounts option: [%s]", errmsg
        )

    try:
        cType = qcowConfig["format-specific"]["data"]["compression-type"]
        opt.append("-o")
        opt.append(f"compression_type={cType}")
        logging.info("Setting image compression type: [%s]", cType)
    except KeyError as errmsg:
        pass

    try:
        dataFile = qcowConfig["format-specific"]["data"]["data-file"]
        if relocatedDataFile:
            dataFilePath = relocatedDataFile
            logging.info(
                "Relocating QCOW data-file backend for disk [%s] from [%s] to [%s]",
                meta["diskName"],
                dataFile,
                dataFilePath,
            )
        elif args.adjust_config is True:
            dataFilePath = os.path.join(
                args.output,
                os.path.basename(dataFile),
            )
            logging.info(
                "QCOW image with data-file backend detected: [%s], adjusting path to: [%s]",
                dataFile,
                dataFilePath,
            )
        else:
            logging.info(
                "QCOW image with data-file backend detected, keeping original path: [%s]",
                dataFile,
            )
            dataFilePath = dataFile

        opt.append("-o")
        opt.append(f"data_file={dataFilePath}")
    except KeyError as errmsg:
        if relocatedDataFile:
            raise RestoreError(
                f"Disk [{meta['diskName']}] does not use a QCOW data-file backend"
            ) from errmsg

    try:
        if qcowConfig["format-specific"]["data"]["data-file-raw"] is True:
            opt.append("-o")
            opt.append("data_file_raw=true")
        logging.info("QCOW image with RAW data-file backend detected.")
    except KeyError as errmsg:
        pass

    return opt


def create(args: Namespace, meta: Dict[str, str], targetFile: str, sshClient):
    """Read QCOW image related backup json and create target image file using
    its original options"""
    options = getConfig(args, meta)
    logging.info(
        "Create virtual disk [%s] format: [%s] size: [%s] based on: [%s] preallocated: [%s]",
        targetFile,
        meta["diskFormat"],
        meta["virtualSize"],
        meta["checkpointName"],
        args.preallocate,
    )

    if lib.exists(args, targetFile):
        logging.error(
            "Target file already exists: [%s], won't overwrite.",
            os.path.abspath(targetFile),
        )
        raise RestoreError

    qFh = qemu.util(meta["diskName"])
    try:
        qFh.create(
            args,
            targetFile,
            int(meta["virtualSize"]),
            meta["diskFormat"],
            options,
            sshClient,
        )
    except (ProcessError, sshError) as e:
        logging.error("Failed to create restore target: [%s]", e)
        raise RestoreError from e
