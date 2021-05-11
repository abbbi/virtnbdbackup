import os
import sys
import glob
import json
import logging

class Common(object):
    """ Common functions
    """
    def __init__(self):
        """ Default values
        """
        self.logFormat = "%(asctime)s %(levelname)s %(module)s - %(funcName)s: %(message)s"
        self.logDateFormat = "%Y-%m-%d %H:%M:%S"
        self.checkpointName = "virtnbdbackup"

    def argparse(self, parser):
        try:
            return parser.parse_args()
        except:
            sys.exit(1)

    def printVersion(self, version):
         logging.info("Version: %s Arguments: %s", version, " ".join(sys.argv))

    def createOutputDir(self, targetDir):
        if targetDir == "-":
            return

        if not os.path.exists(targetDir):
            try:
                os.makedirs(targetDir)
            except OSError as e:
                logging.error("Unable to create target directory: %s", e)
                sys.exit(1)

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
        if os.path.exists(args.output) and args.level in ("full","copy"):
            dirList = [ f for f in glob.glob("%s/*" % args.output) if not os.path.basename(f).endswith(".log") ]
            if len(dirList) > 0:
                return False

        return True

    def getDataFiles(self, targetDir):
        """ return data files within backupset
            directory
        """
        sStr = "%s/*.data" % targetDir
        return glob.glob(sStr)

    def getDataFilesByDisk(self, targetDir, targetDisk):
        """ return data files subject to one disk
            from backupset directory
        """
        sStr = "%s/%s*.data" % (targetDir, targetDisk)
        return glob.glob(sStr)

    def getLastConfigFile(self, targetDir):
        """ get the last backed up configuration file
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

        return json.dumps(extList)

    def dumpMetaData(self, dataFile, sparsestream):
        """ read metadata header
        """
        with open(dataFile, "rb") as reader:
            try:
                kind, start, length = sparsestream.SparseStream().readFrame(
                    reader
                )
            except ValueError:
                return False

            meta = sparsestream.SparseStream().loadMetadata(reader.read(
                length
            ))
            return meta

    def writeChunk(self, writer, offset, length, maxRequestSize, nbdCon, btype):
        """ During extent processing, consecutive blocks with
        the same type(data or zeroed) are unified into one big chunk.
        This helps to reduce requests to the NBD Server.

        But in cases where the block to be saved exceeds the maximum
        recommended request size (nbdClient.maxRequestSize), we
        need to split one big request into multiple not exceeding
        the limit
        """
        blockOffset = offset
        while blockOffset < offset+length:
            blocklen = min(
                offset+length - blockOffset,
                maxRequestSize
            )
            if btype == "raw":
                writer.seek(blockOffset)
            writer.write(nbdCon.pread(blocklen, blockOffset))
            blockOffset+=blocklen

    def zeroChunk(self, offset, length, maxRequestSize, nbdCon):
        zeroOffset = offset
        while zeroOffset < offset+length:
            zeroLen = min(
                offset+length - zeroOffset,
                maxRequestSize
            )
            nbdCon.zero(zeroLen, zeroOffset)
            zeroOffset+=zeroLen

    def readChunk(self, reader, offset, length, maxRequestSize, nbdCon):
        blockOffset = offset
        while blockOffset < offset+length:
            blocklen = min(
                offset+length - blockOffset,
                maxRequestSize
            )
            data = reader.read(blocklen)
            nbdCon.pwrite(data, blockOffset)
            blockOffset+=blocklen
