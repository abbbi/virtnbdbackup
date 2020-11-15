import glob
class Common(object):

    """Docstring for Common. """
    def getDataFiles(self, targetDir):
        sStr = "%s/*.data" % targetDir
        return glob.glob(sStr)
