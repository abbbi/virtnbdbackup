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
import logging
import json
from argparse import Namespace
from typing import List, Dict
from libvirtnbdbackup.qemu import util as qemu
from libvirtnbdbackup import output
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.exceptions import RestoreError
from libvirtnbdbackup.qemu.exceptions import ProcessError
from libvirtnbdbackup.output.exceptions import OutputException
from libvirtnbdbackup.ssh.exceptions import sshError


def getConfig(args: Namespace, meta: Dict[str, str]) -> List[str]:
    """Check if backup includes exported qcow config and return a list
    of options passed to qemu-img create command"""
    opt: List[str] = []
    qcowConfig = None
    qcowConfigFile = lib.getLatest(args.input, f"{meta['diskName']}*.qcow.json*", -1)
    if not qcowConfigFile:
        logging.warning("No qcow image config found, will use default options.")
        return opt

    lastConfigFile = qcowConfigFile[0]

    try:
        with output.openfile(lastConfigFile, "rb") as qFh:
            qcowConfig = json.loads(qFh.read().decode())
        logging.info("Using QCOW options from backup file: [%s]", lastConfigFile)
    except (
        OutputException,
        json.decoder.JSONDecodeError,
    ) as errmsg:
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

    return opt


def create(args: Namespace, meta: Dict[str, str], targetFile: str, sshClient):
    """Create target image file"""
    logging.info(
        "Create virtual disk [%s] format: [%s] size: [%s] based on: [%s] preallocated: [%s]",
        targetFile,
        meta["diskFormat"],
        meta["virtualSize"],
        meta["checkpointName"],
        args.preallocate,
    )

    options = getConfig(args, meta)
    if lib.exists(args, targetFile):
        logging.error("Target file already exists: [%s], won't overwrite.", targetFile)
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
