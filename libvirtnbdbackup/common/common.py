"""
    Copyright (C) 2021  Michael Ablassmeier <abi@grinser.de>

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
import sys
import glob
import json
import logging
import logging.handlers
import signal
import shutil
import pprint
from argparse import Namespace
from typing import Optional, Generator, List, Any, Tuple, IO, Union, Dict
import lz4.frame
from tqdm import tqdm

from libvirtnbdbackup import ssh
from libvirtnbdbackup.ssh.exceptions import sshError
from libvirtnbdbackup import output
from libvirtnbdbackup.logcount import logCount

log = logging.getLogger("lib")

logFormat = (
    "%(asctime)s %(levelname)s %(name)s %(module)s - %(funcName)s"
    " [%(threadName)s]: %(message)s"
)
logDateFormat = "[%Y-%m-%d %H:%M:%S]"
checkpointName = "virtnbdbackup"


def argparse(parser) -> Namespace:
    """Parse arguments"""
    return parser.parse_args()


def printVersion(version) -> None:
    """Print version and passed arguments"""
    log.info("Version: %s Arguments: %s", version, " ".join(sys.argv))


def setLogLevel(verbose: bool) -> int:
    """Set loglevel"""
    level = logging.INFO
    if verbose is True:
        level = logging.DEBUG

    return level


def sshSession(args: Namespace, remoteHost: str) -> Union[ssh.client, None]:
    """Use ssh to copy remote files"""
    try:
        return ssh.client(remoteHost, args.ssh_user)
    except sshError as err:
        log.warning("Failed to setup SSH connection: [%s]", err)

    return None


def getLogFile(fileName: str) -> Optional[logging.FileHandler]:
    """Try setup log handler, if this fails, something is already
    wrong, but we can at least provide correct error message."""
    try:
        return logging.FileHandler(fileName)
    except OSError as e:
        logging.error("Failed to open logfile: [%s].", e)
        return None


def configLogger(
    args: Namespace, fileLog: Optional[logging.FileHandler], counter: logCount
):
    """Setup logging"""
    syslog = False
    try:
        syslog = args.syslog is True
    except AttributeError:
        pass
    handler: List[Any]
    handler = [
        fileLog,
        logging.StreamHandler(stream=sys.stderr),
        counter,
    ]
    if syslog is True:
        handler.append(logging.handlers.SysLogHandler(address="/dev/log"))
    logging.basicConfig(
        level=setLogLevel(args.verbose),
        format=logFormat,
        datefmt=logDateFormat,
        handlers=handler,
    )


def partialBackup(args: Namespace) -> int:
    """Check for possible partial backup files"""
    partialFiles = glob.glob(f"{args.output}/*.partial")
    return len(partialFiles) > 0


def hasFullBackup(args: Namespace) -> int:
    """Check if full backup file exists in target directory"""
    fullFiles = glob.glob(f"{args.output}/*.full.data")
    return len(fullFiles) > 0


def exists(args: Namespace, filePath: str) -> bool:
    """Check if file exists either remotely or locally."""
    if args.sshClient:
        return args.sshClient.exists(filePath)

    return os.path.exists(filePath)


def targetIsEmpty(args: Namespace) -> bool:
    """Check if target directory does not include an backup
    already (no .data or .data.partial files)"""
    if exists(args, args.output) and args.level in ("full", "copy", "auto"):
        dirList = glob.glob(f"{args.output}/*.data*")
        if len(dirList) > 0:
            return False

    return True


def getLatest(targetDir: str, search: str, key=None) -> List[str]:
    """get the last backed up file matching search
    from the backupset, used to find latest vm config,
    data files or data files by disk.
    """
    ret: List[str] = []
    try:
        files = glob.glob(f"{targetDir}/{search}")
        files.sort(key=os.path.getmtime)

        if key is not None:
            ret.append(files[key])
        else:
            ret = files

        log.debug("Sorted data files: \n%s", pprint.pformat(ret))
        return ret
    except IndexError:
        return []


def hasQcowDisks(diskList: List[Any]) -> bool:
    """Check if the list of attached disks include at least one
    qcow image based disk, else checkpoint handling can be
    skipped and backup modue falls back to type copy"""
    for disk in diskList:
        if disk.format == "qcow2":
            return True

    return False


def copy(args: Namespace, source: str, target: str) -> None:
    """Copy file, handle exceptions"""
    try:
        if args.sshClient:
            args.sshClient.copy(source, target)
        else:
            shutil.copyfile(source, target)
    except OSError as e:
        log.warning("Failed to copy [%s] to [%s]: [%s]", source, target, e)
    except sshError as e:
        log.warning("Remote copy from [%s] to [%s] failed: [%s]", source, target, e)


def progressBar(total: int, desc: str, args: Namespace, count=0) -> tqdm:
    """Return tqdm object"""
    return tqdm(
        total=total,
        desc=desc,
        unit="B",
        unit_scale=True,
        disable=args.noprogress,
        position=count,
        leave=False,
    )


def killProc(pid: int) -> bool:
    """Attempt kill PID"""
    log.debug("Killing PID: %s", pid)
    while True:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except ProcessLookupError:
            return True


def dumpExtentJson(extents) -> str:
    """Dump extent object as json"""
    extList = []
    for extent in extents:
        ext = {}
        ext["start"] = extent.offset
        ext["length"] = extent.length
        ext["data"] = extent.data
        extList.append(ext)

    return json.dumps(extList, indent=4, sort_keys=True)


def dumpMetaData(dataFile: str, stream):
    """read metadata header"""
    with output.openfile(dataFile, "rb") as reader:
        _, _, length = stream.readFrame(reader)
        return stream.loadMetadata(reader.read(length))


def blockStep(offset: int, length: int, maxRequestSize: int) -> Generator:
    """Process block and ensure to not exceed the maximum request size
    from NBD server.

    If length parameter is dict, compression was enabled during
    backup, thus we cannot use the offsets and sizes for the
    original data, but must use the compressed offsets and sizes
    to read the correct lz4 frames from the stream.
    """
    blockOffset = offset
    if isinstance(length, dict):
        blockOffset = offset
        compressOffset = list(length.keys())[0]
        for step in length[compressOffset]:
            blockOffset += step
            yield step, blockOffset
    else:
        blockOffset = offset
        while blockOffset < offset + length:
            blocklen = min(offset + length - blockOffset, maxRequestSize)
            yield blocklen, blockOffset
            blockOffset += blocklen


def isCompressed(meta: Dict[str, str]) -> bool:
    """Return true if stream is compressed"""
    try:
        version = meta["stream-version"] == 2
    except KeyError:
        version = meta["streamVersion"] == 2

    if version:
        if meta["compressed"] is not False:
            return True

    return False


def lz4DecompressFrame(data: bytes) -> bytes:
    """Decompress lz4 frame, print frame information"""
    frameInfo = lz4.frame.get_frame_info(data)
    log.debug("Compressed Frame: %s", frameInfo)
    return lz4.frame.decompress(data)


def lz4CompressFrame(data: bytes, level: int) -> bytes:
    """Compress block with to lz4 frame, checksums
    enabled for safety
    """
    return lz4.frame.compress(
        data,
        content_checksum=True,
        block_checksum=True,
        compression_level=level,
    )


def writeChunk(
    writer: IO[Any], block, nbdCon, btype, compress
) -> Tuple[int, List[int]]:
    """During extent processing, consecutive blocks with
    the same type(data or zeroed) are unified into one big chunk.
    This helps to reduce requests to the NBD Server.

    But in cases where the block to be saved exceeds the maximum
    recommended request size (nbdClient.maxRequestSize), we
    need to split one big request into multiple not exceeding
    the limit

    If compression is enabled, function returns a list of
    offsets for the compressed frames, which is appended
    to the end of the stream.
    """
    wSize = 0
    cSizes = []
    for blocklen, blockOffset in blockStep(
        block.offset, block.length, nbdCon.maxRequestSize
    ):
        if btype == "raw":
            writer.seek(blockOffset)

        data = nbdCon.nbd.pread(blocklen, blockOffset)

        if compress is not False and btype != "raw":
            compressed = lz4CompressFrame(data, compress)
            wSize += writer.write(compressed)
            cSizes.append(len(compressed))
        else:
            wSize += writer.write(data)

    return wSize, cSizes


def writeBlock(writer: IO[Any], block, nbdCon, btype: str, compress: bool) -> int:
    """Write single block that does not exceed nbd maxRequestSize
    setting. In case compression is enabled, single blocks are
    compressed using lz4.block.
    """
    if btype == "raw":
        writer.seek(block.offset)
    data = nbdCon.nbd.pread(block.length, block.offset)

    if compress is not False and btype != "raw":
        data = lz4CompressFrame(data, compress)

    return writer.write(data)


def readChunk(
    reader: IO[Any],
    offset: int,
    length: int,
    nbdCon,
    compression: int,
) -> int:
    """Read data from reader and write to nbd connection

    If Compression is enabled function receives length information
    as dict, which contains the stream offsets for the compressed
    lz4 frames.

    Frames are read from the stream at the compressed size information
    (offset in the stream).

    After decompression, data is written back to original offset
    in the virtual machine disk image.

    If no compression is enabled, data is read from the regular
    data header at its position and written to nbd target
    directly.
    """
    wSize = 0
    for blocklen, blockOffset in blockStep(offset, length, nbdCon.maxRequestSize):
        if compression is True:
            data = lz4DecompressFrame(reader.read(blocklen))
            nbdCon.nbd.pwrite(data, offset)
            offset += len(data)
            wSize += len(data)
        else:
            data = reader.read(blocklen)
            nbdCon.nbd.pwrite(data, blockOffset)
            wSize += len(data)

    return wSize
