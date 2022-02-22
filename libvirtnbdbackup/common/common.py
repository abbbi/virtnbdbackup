"""
    Common functions
"""
import os
import sys
import glob
import json
import logging
import signal
import pprint
import lz4.frame
from tqdm import tqdm

log = logging.getLogger(__name__)


class Common:
    """Common functions"""

    def __init__(self):
        """Default values"""
        self.logFormat = (
            "%(asctime)s %(levelname)s %(module)s - %(funcName)s"
            " [%(threadName)s]: %(message)s"
        )
        self.logDateFormat = "[%Y-%m-%d %H:%M:%S]"
        self.checkpointName = "virtnbdbackup"

    @staticmethod
    def argparse(parser):
        """Parse arguments"""
        return parser.parse_args()

    @staticmethod
    def printVersion(version):
        """Print version and passed arguments"""
        log.info("Version: %s Arguments: %s", version, " ".join(sys.argv))

    @staticmethod
    def setLogLevel(verbose):
        """Set loglevel"""
        if verbose is True:
            level = logging.DEBUG
        else:
            level = logging.INFO

        return level

    @staticmethod
    def getSocketFile(arg):
        """Return used socket file name"""
        if not arg:
            socketFile = f"/var/tmp/virtnbdbackup.{os.getpid()}"
        else:
            socketFile = arg

        return socketFile

    @staticmethod
    def partialBackup(args):
        """Check for possible partial backup files"""
        partialFiles = glob.glob(f"{args.output}/*.partial")
        if len(partialFiles) > 0:
            return True

        return False

    @staticmethod
    def targetIsEmpty(args):
        """Check if target directory is empty"""
        if os.path.exists(args.output) and args.level in ("full", "copy"):
            dirList = [
                f
                for f in glob.glob(f"{args.output}/*")
                if not os.path.basename(f).endswith(".log")
            ]
            if len(dirList) > 0:
                return False

        return True

    @staticmethod
    def getDataFiles(targetDir):
        """return data files within backupset
        directory
        """
        files = glob.glob(f"{targetDir}/*.data")
        files.sort(key=os.path.getmtime)

        log.debug("Sorted data files: \n%s", pprint.pformat(files))
        return files

    @staticmethod
    def getDataFilesByDisk(targetDir, targetDisk):
        """return data files subject to one disk
        from backupset directory
        """
        files = glob.glob(f"{targetDir}/{targetDisk}*.data")
        files.sort(key=os.path.getmtime)

        log.debug(
            "Sorted file list for disk [%s]: \n%s", targetDisk, pprint.pformat(files)
        )
        return files

    @staticmethod
    def getLastConfigFile(targetDir):
        """get the last backed up configuration file
        from the backupset
        """
        try:
            files = glob.glob(f"{targetDir}/vmconfig*.xml")
            files.sort(key=os.path.getmtime)
            return files[-1]
        except IndexError:
            return None

    @staticmethod
    def progressBar(total, desc, args, count=0):
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

    @staticmethod
    def killNbdServer(socketFile):
        """Attempt kill PID"""
        pidFile = f"{socketFile}.pid"
        with open(pidFile, "rb") as pidfh:
            pid = int(pidfh.read())
        os.remove(pidFile)

        logging.debug("Killing PID: %s", pid)
        while True:
            try:
                os.kill(pid, signal.SIGTERM)
                return True
            except ProcessLookupError:
                return True

    @staticmethod
    def dumpExtentJson(extents):
        """Dump extent object as json"""
        extList = []
        for extent in extents:
            ext = {}
            ext["start"] = extent.offset
            ext["length"] = extent.length
            ext["data"] = extent.data
            extList.append(ext)

        return json.dumps(extList, indent=4, sort_keys=True)

    @staticmethod
    def dumpMetaData(dataFile, stream):
        """read metadata header"""
        with open(dataFile, "rb") as reader:
            try:
                _, _, length = stream.readFrame(reader)
            except ValueError:
                return False

            return stream.loadMetadata(reader.read(length))

    @staticmethod
    def blockStep(offset, length, maxRequestSize):
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
            item = next(iter(length))
            for step in length[item]:
                blockOffset += step
                yield step, blockOffset
        else:
            blockOffset = offset
            while blockOffset < offset + length:
                blocklen = min(offset + length - blockOffset, maxRequestSize)
                yield blocklen, blockOffset
                blockOffset += blocklen

    @staticmethod
    def isCompressed(meta):
        """Return true if stream is compressed"""
        try:
            version = meta["stream-version"] == 2
        except KeyError:
            version = meta["streamVersion"] == 2

        if version:
            if meta["compressed"] is True:
                return True

        return False

    @staticmethod
    def lz4DecompressFrame(data):
        """Decompress lz4 frame, print frame information"""
        frameInfo = lz4.frame.get_frame_info(data)
        log.debug("Compressed Frame: %s", frameInfo)
        return lz4.frame.decompress(data)

    @staticmethod
    def lz4CompressFrame(data):
        """Compress block with to lz4 frame, checksums
        enabled for safety
        """
        return lz4.frame.compress(data, content_checksum=True, block_checksum=True)

    def writeChunk(
        self, writer, offset, length, maxRequestSize, nbdCon, btype, compress
    ):
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
        for blocklen, blockOffset in self.blockStep(offset, length, maxRequestSize):
            if btype == "raw":
                writer.seek(blockOffset)

            data = nbdCon.pread(blocklen, blockOffset)

            if compress is True and btype != "raw":
                compressed = self.lz4CompressFrame(data)
                wSize += writer.write(compressed)
                cSizes.append(len(compressed))
            else:
                wSize += writer.write(data)

        return wSize, cSizes

    def writeBlock(self, writer, offset, length, nbdCon, btype, compress):
        """Write single block that does not exceed nbd maxRequestSize
        setting. In case compression is enabled, single blocks are
        compressed using lz4.block.
        """
        if btype == "raw":
            writer.seek(offset)
        data = nbdCon.pread(length, offset)

        if compress is True and btype != "raw":
            data = self.lz4CompressFrame(data)

        return writer.write(data)

    def zeroChunk(self, offset, length, maxRequestSize, nbdCon):
        """Write zeroes using libnbd zero function"""
        for zeroLen, zeroOffset in self.blockStep(offset, length, maxRequestSize):
            nbdCon.zero(zeroLen, zeroOffset)

    def readChunk(self, reader, offset, length, maxRequestSize, nbdCon, compression):
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
        for blocklen, blockOffset in self.blockStep(offset, length, maxRequestSize):
            if compression is True:
                data = self.lz4DecompressFrame(reader.read(blocklen))
                nbdCon.pwrite(data, offset)
                offset += len(data)
                wSize += len(data)
            else:
                data = reader.read(blocklen)
                nbdCon.pwrite(data, blockOffset)
                wSize += len(data)

        return wSize
