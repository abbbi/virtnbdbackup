import glob
import json

class Common(object):
    """
        Common functions
    """
    def getDataFiles(self, targetDir):
        """
            return data files within backupset
            directory
        """
        sStr = "%s/*.data" % targetDir
        return glob.glob(sStr)

    def getDataFilesByDisk(self, targetDir, targetDisk):
        """
            return data files subject to one disk
            from backupset directory
        """
        sStr = "%s/%s*.data" % (targetDir, targetDisk)
        return glob.glob(sStr)

    def getLastConfigFile(self, targetDir):
        """
            get the last backed up configuration file
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
        """
            read metadata header
        """
        with open(dataFile, 'rb') as reader:
            try:
                kind, start, length = sparsestream.SparseStream().read_frame(
                    reader
                )
            except ValueError:
                return False

            meta = sparsestream.SparseStream().load_metadata(reader.read(
                length
            ))
            return meta

