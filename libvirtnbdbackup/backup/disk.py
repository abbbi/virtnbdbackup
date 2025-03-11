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
from argparse import Namespace
from typing import List, Any, Tuple
from libvirtnbdbackup import nbdcli
from libvirtnbdbackup import virt
from libvirtnbdbackup.virt.client import DomainDisk
from libvirtnbdbackup.objects import processInfo
from libvirtnbdbackup.sparsestream import streamer
from libvirtnbdbackup.sparsestream import types
from libvirtnbdbackup import exceptions
from libvirtnbdbackup import chunk
from libvirtnbdbackup import block
from libvirtnbdbackup.backup import partialfile
from libvirtnbdbackup.backup import server
from libvirtnbdbackup.backup import target
from libvirtnbdbackup.backup.metadata import backupChecksum
from libvirtnbdbackup import extenthandler
from libvirtnbdbackup.qemu import util as qemu
from libvirtnbdbackup.qemu.exceptions import ProcessError
from libvirtnbdbackup import common as lib
from libvirtnbdbackup import output
from libvirtnbdbackup.output import stream


def _setStreamType(args: Namespace, disk: DomainDisk) -> str:
    """Set target stream type based on disk format"""
    streamType = "raw"
    if disk.format != streamType:
        streamType = args.type

    return streamType


def _getExtentHandler(args: Namespace, nbdClient):
    """Query dirty blocks either via qemu client or self
    implemented extend handler"""
    if args.qemu:
        logging.info("Using qemu tools to query extents")
        extentHandler = extenthandler.ExtentHandler(
            qemu.util(nbdClient.cType.exportName), nbdClient.cType
        )
    else:
        extentHandler = extenthandler.ExtentHandler(nbdClient, nbdClient.cType)

    return extentHandler


def backup(  # pylint: disable=too-many-arguments,too-many-branches, too-many-locals, too-many-statements
    args: Namespace,
    disk: DomainDisk,
    count: int,
    fileStream,
    virtClient: virt.client,
) -> Tuple[int, bool]:
    """Backup domain disk data."""
    dStream = streamer.SparseStream(types)
    sTypes = types.SparseStreamTypes()
    lib.setThreadName(disk.target)
    streamType = _setStreamType(args, disk)
    metaContext = nbdcli.context.get(args, disk)
    nbdProc: processInfo
    remoteIP: str = virtClient.remoteHost
    port: int = args.nbd_port
    if args.nbd_ip != "":
        remoteIP = args.nbd_ip

    if args.offline is True:
        port = args.nbd_port + count
        try:
            nbdProc = server.setup(args, disk, virtClient.remoteHost, port)
        except ProcessError as errmsg:
            logging.error(errmsg)
            raise exceptions.DiskBackupFailed("Failed to start NBD server.")

    if disk.discardOption is not None:
        logging.info("Virtual disk discard option: [%s]", disk.discardOption)

    connection = server.connect(args, disk, metaContext, remoteIP, port, virtClient)

    extentHandler = _getExtentHandler(args, connection)
    extents = extentHandler.queryBlockStatus()
    diskSize = connection.nbd.get_size()

    if extents is None:
        logging.error("No extents returned by NBD server.")
        return 0, False

    thinBackupSize = sum(extent.length for extent in extents if extent.data is True)
    logging.info("Got %s extents to backup.", len(extents))
    logging.debug("%s", lib.dumpExtentJson(extents))
    logging.info("%s bytes disk size", diskSize)
    logging.info("%s bytes of data extents to backup", thinBackupSize)

    if args.level in ("inc", "diff") and thinBackupSize == 0:
        logging.info("No dirty blocks found")
        args.noprogress = True

    targetFile, targetFilePartial = target.Set(args, disk)

    # if writing to regular files we want instantiate an new
    # handle for each file otherwise multiple threads collid
    # during file close
    # in case of zip file output we want to use the existing
    # opened output channel
    if not args.stdout:
        fileStream = stream.get(args, output.target())
    writer = target.get(args, fileStream, targetFile, targetFilePartial)

    if streamType == "raw":
        logging.info("Creating full provisioned raw backup image")
        writer.truncate(diskSize)
    else:
        logging.info("Creating thin provisioned stream backup image")
        header = dStream.dumpMetadata(
            args,
            diskSize,
            thinBackupSize,
            disk,
        )
        dStream.writeFrame(writer, sTypes.META, 0, len(header))
        writer.write(header)
        writer.write(sTypes.TERM)

    progressBar = lib.progressBar(
        thinBackupSize, f"saving disk {disk.target}", args, count=count
    )
    compressedSizes: List[Any] = []
    backupSize: int = 0
    for save in extents:
        if save.data is True:
            if streamType == "stream":
                dStream.writeFrame(writer, sTypes.DATA, save.offset, save.length)
                logging.debug(
                    "Read data from: start %s, length: %s", save.offset, save.length
                )

            cSizes = None

            if save.length >= connection.maxRequestSize:
                logging.debug(
                    "Chunked data read from: start %s, length: %s",
                    save.offset,
                    save.length,
                )
                size, cSizes = chunk.write(
                    writer, save, connection, streamType, args.compress, progressBar
                )
            else:
                size = block.write(
                    writer,
                    save,
                    connection,
                    streamType,
                    args.compress,
                )
                if streamType == "raw":
                    size = writer.seek(save.offset)

                progressBar.update(save.length)

            if streamType == "stream":
                writer.write(sTypes.TERM)
                if args.compress:
                    logging.debug("Compressed size: %s", size)
                    backupSize += size
                    if cSizes:
                        blockList = {}
                        blockList[size] = cSizes
                        compressedSizes.append(blockList)
                    else:
                        compressedSizes.append(size)
                else:
                    assert size == save.length
                    backupSize += save.length
        else:
            if streamType == "raw":
                writer.seek(save.offset)
                backupSize += save.length
            elif streamType == "stream" and args.level not in ("inc", "diff"):
                dStream.writeFrame(writer, sTypes.ZERO, save.offset, save.length)
    if streamType == "stream":
        dStream.writeFrame(writer, sTypes.STOP, 0, 0)
        if args.compress:
            dStream.writeCompressionTrailer(writer, compressedSizes)

    progressBar.close()
    writer.close()
    connection.disconnect()

    if args.offline is True and virtClient.remoteHost == "":
        logging.info("Stopping NBD Service.")
        lib.killProc(nbdProc.pid)

    if args.offline is True:
        lib.remove(args, nbdProc.pidFile)

    if not args.stdout:
        if args.noprogress is True:
            logging.info(
                "Backup of disk [%s] finished, file: [%s]", disk.target, targetFile
            )
        partialfile.rename(targetFilePartial, targetFile)
        backupChecksum(fileStream, targetFile)

    return backupSize, True
