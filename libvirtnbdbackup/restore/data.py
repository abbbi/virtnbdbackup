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
import pprint
from argparse import Namespace
from libvirtnbdbackup import chunk
from libvirtnbdbackup import lz4
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.sparsestream import types
from libvirtnbdbackup.sparsestream import streamer
from libvirtnbdbackup.sparsestream.exceptions import StreamFormatException
from libvirtnbdbackup.exceptions import RestoreError
from libvirtnbdbackup.exceptions import UntilCheckpointReached


def restore(
    args: Namespace,
    stream: streamer.SparseStream,
    disk: str,
    targetFile: str,
    connection,
) -> bool:
    """Restore the data stream to the target file"""
    diskState = False
    diskState = _write(args, stream, disk, targetFile, connection)
    # no data has been processed
    if diskState is None:
        diskState = True

    return diskState


def _write(  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    args: Namespace,
    stream: streamer.SparseStream,
    dataFile: str,
    targetFile: str,
    connection,
) -> bool:
    """Restore data for disk"""
    sTypes = types.SparseStreamTypes()

    try:
        # pylint: disable=consider-using-with
        reader = open(dataFile, "rb")
    except OSError as errmsg:
        logging.error("Failed to open backup file for reading: [%s].", errmsg)
        raise RestoreError from errmsg

    try:
        kind, start, length = stream.readFrame(reader)
        meta = stream.loadMetadata(reader.read(length))
    except StreamFormatException as errmsg:
        logging.fatal(errmsg)
        raise RestoreError from errmsg

    trailer = None
    if lib.isCompressed(meta) is True:
        trailer = stream.readCompressionTrailer(reader)
        logging.info("Found compression trailer.")
        logging.debug("%s", trailer)

    if meta["dataSize"] == 0:
        logging.info("File [%s] contains no dirty blocks, skipping.", dataFile)
        if meta["checkpointName"] == args.until:
            logging.info("Reached checkpoint [%s], stopping", args.until)
            raise UntilCheckpointReached
        return True

    logging.info(
        "Applying data from backup file [%s] to target file [%s].", dataFile, targetFile
    )
    pprint.pprint(meta)
    assert reader.read(len(sTypes.TERM)) == sTypes.TERM

    progressBar = lib.progressBar(
        meta["dataSize"], f"restoring disk [{meta['diskName']}]", args
    )
    dataSize: int = 0
    dataBlockCnt: int = 0
    while True:
        try:
            kind, start, length = stream.readFrame(reader)
        except StreamFormatException as err:
            logging.error("Can't read stream at pos: [%s]: [%s]", reader.tell(), err)
            raise RestoreError from err
        if kind == sTypes.ZERO:
            logging.debug("Zero segment from [%s] length: [%s]", start, length)
        elif kind == sTypes.DATA:
            logging.debug(
                "Processing data segment from [%s] length: [%s]", start, length
            )

            originalSize = length
            if trailer:
                logging.debug("Block: [%s]", dataBlockCnt)
                logging.debug("Original block size: [%s]", length)
                length = trailer[dataBlockCnt]
                logging.debug("Compressed block size: [%s]", length)

            if originalSize >= connection.maxRequestSize:
                logging.debug(
                    "Chunked read/write, start: [%s], len: [%s]", start, length
                )
                try:
                    written = chunk.read(
                        reader,
                        start,
                        length,
                        connection,
                        lib.isCompressed(meta),
                        progressBar,
                    )
                except Exception as e:
                    logging.exception(e)
                    raise RestoreError from e
                logging.debug("Wrote: [%s]", written)
            else:
                try:
                    data = reader.read(length)
                    if lib.isCompressed(meta):
                        data = lz4.decompressFrame(data)
                    connection.nbd.pwrite(data, start)
                    written = len(data)
                except Exception as e:
                    logging.exception(e)
                    raise RestoreError from e
                progressBar.update(written)

            assert reader.read(len(sTypes.TERM)) == sTypes.TERM
            dataSize += originalSize
            dataBlockCnt += 1
        elif kind == sTypes.STOP:
            progressBar.close()
            if dataSize != meta["dataSize"]:
                logging.error(
                    "Restored data size does not match [%s] != [%s]",
                    dataSize,
                    meta["dataSize"],
                )
                raise RestoreError("Data size mismatch")
            break

    logging.info("End of stream, [%s] of data processed", lib.humanize(dataSize))
    if meta["checkpointName"] == args.until:
        logging.info("Reached checkpoint [%s], stopping", args.until)
        raise UntilCheckpointReached

    if connection.nbd.can_flush() is True:
        logging.debug("Flushing NBD connection handle")
        connection.nbd.flush()

    return True
