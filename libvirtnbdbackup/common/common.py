import glob
class Common(object):

    """Docstring for Common. """
    def getDataFiles(self, targetDir):
        sStr = "%s/*.data" % targetDir
        return glob.glob(sStr)

    def getDataFilesByDisk(self, targetDir, targetDisk):
        sStr = "%s/%s*.data" % (targetDir, targetDisk)
        return glob.glob(sStr)

    def getLastConfigFile(self, targetDir):
        sStr = "%s/vmconfig*.xml" % targetDir
        try:
            return glob.glob(sStr)[-1]
        except IndexError:
            return None

    def dumpMetaData(self, dataFile, sparsestream):
        with open(dataFile, 'rb') as reader:
            kind, start, length = sparsestream.SparseStream().read_frame(
                reader
            )
            meta = sparsestream.SparseStream().load_metadata(reader.read(
                length
            ))
            return meta

