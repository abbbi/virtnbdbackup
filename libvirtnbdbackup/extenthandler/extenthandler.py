import logging

class Extent(object):
    def __init__(self):
        self.data = False
        self.zero = False
        self.length = 0
        self.offset = 0

class _ExtentObj(object):
    def __init__(self):
        self.length = None
        self.type = None

class ExtentHandler(object):
    """ Query extent information about allocated and
        zeroed regions from the NBD server started by
        libvirt/qemu

        This implementation should return the same
        extent information as nbdinfo or qemu-img map
    """
    def __init__(self, nbdFh, metaContext, backupSocket):
        self. useQemu = False
        if nbdFh.__class__.__name__ == "qemuHelper":
            self.useQemu = True

        self._socket = backupSocket
        self._nbdFh = nbdFh
        self._extentEntries = []
        if metaContext == None:
            self._metaContext = "base:allocation"
        else:
            self._metaContext = metaContext

        logging.debug("Meta context: %s" % self._metaContext)
        self._maxRequestBlock = 4294967295
        self._align = 512

    def _getExtentCallback(self, metacontext, offset, entries, status):
        logging.debug("Metacontext is: %s" % metacontext)
        if metacontext != self._metaContext:
            logging.error("Meta context does not match")
            return
        for entry in entries:
            self._extentEntries.append(entry)
        logging.debug("entries: %s" % len(self._extentEntries))

    def _setRequestAligment(self):
        align = self._nbdFh.get_block_size(0)
        if align == 0:
            align = self._align
        return self._maxRequestBlock - align + 1

    def queryExtents(self):
        if self.useQemu:
            return self.queryExtentsQemu()

        return self.queryExtentsNbd()

    def queryExtentsQemu(self):
        extents = []
        for extent in self._nbdFh.map(self._socket):
            extentObj = Extent()
            if extent['data'] == True:
                extentObj.data = True
            else:
                extentObj.data = False
            extentObj.offset = extent['start']
            extentObj.length = extent['length']
            extents.append(extentObj)

        logging.debug("Got %s extents from qemu command" % len(extents))

        return extents

    def _extentsToObj(self):
        extentSizes = self._extentEntries[0::2]
        extentTypes = self._extentEntries[1::2]
        assert len(extentSizes) == len(extentTypes)
        ct = 0
        extentList = []
        while ct < len(extentSizes):
            extentObj = _ExtentObj()
            extentObj.length = extentSizes[ct]
            extentObj.type = extentTypes[ct]
            extentList.append(extentObj)
            ct+=1

        return extentList

    def _unifyExtents(self, extentObjects):
        logging.debug("unify %s extents" % len(extentObjects))
        cur = None
        for myExtent in extentObjects:
            if cur == None:
                cur = myExtent
            elif cur.type == myExtent.type:
                cur.length += myExtent.length
            else:
                yield cur
                cur = myExtent

        yield cur

    def queryExtentsNbd(self):
        maxRequestLen = self._setRequestAligment()
        offset = 0
        size = self._nbdFh.get_size()
        logging.debug("Size returned from NDB server: %s" % size)
        lastExtentLen = len(self._extentEntries)
        while offset < size:
            if size < maxRequestLen:
                request_length=size
            else:
                request_length = min(size - offset, maxRequestLen)
            logging.debug('Block status request length: %s' % request_length)
            self._nbdFh.block_status(request_length, offset, self._getExtentCallback)
            if len(self._extentEntries) == 0:
                logging.error("No extents found")
                return False

            offset+=sum(self._extentEntries[lastExtentLen::2])
            lastExtentLen = len(self._extentEntries)

        logging.debug('Extents: %s' % self._extentEntries)
        logging.debug('Number Extents: %s' % len(self._extentEntries))

        return self._extentsToObj()

    def queryBlockStatus(self, extentList=None):
        if self.useQemu == True:
            return self.queryExtentsQemu()

        extentList = []
        start = 0
        for extent in self._unifyExtents(self.queryExtentsNbd()):
            extObj = Extent()
            if self._metaContext == "base:allocation":
                assert extent.type in (0,1,2,3)
                if extent.type == 0:
                    extObj.data = True
                if extent.type == 1:
                    extObj.data = False
                elif extent.type == 2:
                    extObj.data = True
                elif extent.type == 3:
                    extObj.data = False
            else:
                assert extent.type in (0,1)
                if extent.type == 1:
                    extObj.data = True
                else:
                    extObj.data = False

            extObj.offset = start
            extObj.length = extent.length
            extentList.append(extObj)
            start+=extent.length

        logging.debug('Returning extent list with %s objects' % len(extentList))
        return extentList
