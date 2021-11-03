import os
import sys
import glob
import json
import logging
import lz4.frame

log = logging.getLogger(__name__)


class Common:
    """Common functions"""

    def __init__(self):
        """Default values"""
        self.logFormat = "%(asctime)s %(levelname)s %(module)s - %(funcName)s [%(threadName)s]: %(message)s"
        self.logDateFormat = "[%Y-%m-%d %H:%M:%S]"
        self.checkpointName = "virtnbdbackup"

    def argparse(self, parser):
        return parser.parse_args()

    def printVersion(self, version):
        log.info("Version: %s Arguments: %s", version, " ".join(sys.argv))

    def setLogLevel(self, verbose):
        if verbose is True:
            level = logging.DEBUG
        else:
            level = logging.INFO

        return level

    def getSocketFile(self, arg):
        if not arg:
            socketFile = "/var/tmp/virtnbdbackup.%s" % os.getpid()
        else:
            socketFile = arg

        return socketFile

    def partialBackup(self, args):
        partialFiles = glob.glob("%s/*.partial" % args.output)
        if len(partialFiles) > 0:
            return True

        return False

    def targetIsEmpty(self, args):
        if os.path.exists(args.output) and args.level in ("full", "copy"):
            dirList = [
                f
                for f in glob.glob("%s/*" % args.output)
                if not os.path.basename(f).endswith(".log")
            ]
            if len(dirList) > 0:
                return False

        return True

    def getDataFiles(self, targetDir):
        """return data files within backupset
        directory
        """
        sStr = "%s/*.data" % targetDir
        files = glob.glob(sStr)
        files.sort(key=os.path.getmtime)

        return files

    def getDataFilesByDisk(self, targetDir, targetDisk):
        """return data files subject to one disk
        from backupset directory
        """
        sStr = "%s/%s*.data" % (targetDir, targetDisk)
        files = glob.glob(sStr)
        files.sort(key=os.path.getmtime)
        return files

    def getLastConfigFile(self, targetDir):
        """get the last backed up configuration file
        from the backupset
        """
        sStr = "%s/vmconfig*.xml" % targetDir
        try:
            return glob.glob(sStr)[-1]
        except IndexError:
            return None

    def dumpExtentJson(self, extents):
        extList = []
        for extent in extents:
            ext = {}
            ext["start"] = extent.offset
            ext["length"] = extent.length
            ext["data"] = extent.data
            extList.append(ext)

        return json.dumps(extList, indent=4, sort_keys=True)

    def dumpMetaData(self, dataFile, stream):
        """read metadata header"""
        with open(dataFile, "rb") as reader:
            try:
                kind, start, length = stream.readFrame(reader)
            except ValueError:
                return False

            return stream.loadMetadata(reader.read(length))

    def blockStep(self, offset, length, maxRequestSize):
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

    def isCompressed(self, meta):
        """Return true if stream is compressed"""
        try:
            version = meta["stream-version"] == 2
        except:
            version = meta["streamVersion"] == 2

        if version:
            if meta["compressed"] is True:
                return True

        return False

    def lz4DecompressFrame(self, data):
        """Decompress lz4 frame, print frame information"""
        frameInfo = lz4.frame.get_frame_info(data)
        log.debug("Compressed Frame: %s", frameInfo)
        return lz4.frame.decompress(data)

    def lz4CompressFrame(self, data):
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
