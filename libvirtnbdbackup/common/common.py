import os
import sys
import glob
import json

class Common(object):
    """ Common functions
    """

    def argparse(self, parser):
        try:
            return parser.parse_args()
        except:
            sys.exit(1)

    def targetIsEmpty(self, args):
        if os.path.exists(args.output) and args.level in ("full","copy"):
            dirList = os.listdir(args.output)
            if len(dirList) > 1 and not '.log' in dirList:
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
            ext['start'] = extent.offset
            ext['length'] = extent.length
            ext['data'] = extent.data
            extList.append(ext)

        return json.dumps(extList)

    def dumpMetaData(self, dataFile, sparsestream):
        """ read metadata header
        """
        with open(dataFile, 'rb') as reader:
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
        blockOffset = offset
        while blockOffset < offset+length:
            blocklen = min(offset+length - blockOffset,
                           maxRequestSize
                        )
            if btype == "raw":
                writer.seek(blockOffset)
            writer.write(nbdCon.pread(blocklen, blockOffset))
            blockOffset+=blocklen

    def zeroChunk(self, offset, length, maxRequestSize, nbdCon):
        zeroOffset = offset
        while zeroOffset < offset+length:
            zeroLen = min(offset+length - zeroOffset,
                maxRequestSize
            )
            nbdCon.zero(zeroLen, zeroOffset)
            zeroOffset+=zeroLen

    def readChunk(self, reader, offset, length, maxRequestSize, nbdCon):
        blockOffset = offset
        while blockOffset < offset+length:
            blocklen = min(offset+length - blockOffset,
                maxRequestSize
            )
            data = reader.read(blocklen)
            nbdCon.pwrite(data, blockOffset)
            blockOffset+=blocklen
